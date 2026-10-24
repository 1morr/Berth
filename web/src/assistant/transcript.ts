import type { Chunk, Message, NoticePart, PagePart, ToolOutcome } from '../api/assistant'

/**
 * 存下來的那幾則（加上正在串流的那一段）→ 畫面上的一塊一塊（`.scratch/m5/side-panel-shape.md` §3）。
 *
 * 一句使用者的話一塊；它之後、下一句之前的模型回合、工具結果與 notice 收成同一塊「助理」——
 * 一則訊息之後模型可以來回好幾輪，畫面上仍是它回的那一次。工具的狀態行把呼叫與結果以 call id 接起來：
 * 有呼叫沒結果是「正在查」，結果是 `Refusal` 是「沒做成」，變成確認卡的是「等你按」（票 10）。結果本身
 * 跟著那一行走，卡片從它畫（票 09）；之後有人在卡上撤銷了（票 11），撤掉了什麼也接到同一行。
 */

type ToolState = 'running' | 'done' | 'refused' | 'proposed'

/** 工具的結果（存下的 `ToolResultPart` 與串流的 `tool-output-available` 同形）：結果卡從它畫（票 09）。 */
export interface ToolOutput {
  /** 結果型別的名字。舊版本存下的可能不在這一版的 `ToolResultType` 裡。 */
  type: string
  result: Record<string, unknown>
}

export type Item =
  | { kind: 'text'; key: string; text: string }
  | {
      kind: 'tool'
      key: string
      /** 這一次呼叫的 id：結果卡上的撤銷指著它（M5 票 11）。 */
      callId: string
      /**
       * 存著結果的那一則的 id：撤銷指的是「那一則裡的那一次」（有的 provider 每一輪都用同一個 call id）。
       * 還在串流、還沒存下來是 `null`。
       */
      messageId: number | null
      name: string
      state: ToolState
      reason: string
      /** 拒絕的原文（`Refusal.detail`）：理由那一句引它（規則、預估的季集）。 */
      detail: string
      /** 還在跑時是 `null`。 */
      output: ToolOutput | null
      /** 有人在卡上撤銷了：撤掉了什麼（M5 票 11）。沒撤銷是 `null`。 */
      undone: ToolOutput | null
    }
  | { kind: 'notice'; key: string; notice: NoticePart }

export type Block =
  | {
      kind: 'user'
      key: string
      text: string
      /** 說這句話時正在看的作品（M5 票 12）：模型拿到的就是它。不在作品頁是 `null`。 */
      page: PagePart | null
    }
  | { kind: 'assistant'; key: string; items: Item[]; busy: boolean }

/** 送出之後、`finish` 之前那一段：使用者的話與串流到的東西。 */
export interface Pending {
  text: string
  /** 送出時畫面上最後一則的 id：重讀到的、比它新的那幾則由這一段代畫，避免同一句出現兩次。 */
  after: number
  items: Item[]
}

export function blocksOf(messages: Message[], pending: Pending | null): Block[] {
  const shown = pending ? messages.filter((message) => message.id <= pending.after) : messages
  const blocks: Block[] = []
  const tools = new Map<string, Extract<Item, { kind: 'tool' }>>()
  /** 存下的結果，以「那一則：那一次」查（撤銷那一則指著它）。 */
  const results = new Map<string, Extract<Item, { kind: 'tool' }>>()

  const reply = (key: string): Extract<Block, { kind: 'assistant' }> => {
    const last = blocks.at(-1)
    if (last?.kind === 'assistant') return last
    const block = { kind: 'assistant' as const, key, items: [], busy: false }
    blocks.push(block)
    return block
  }

  for (const message of shown) {
    // 頁面那一段排在同一則的話前面（後端 `PagePart`）。
    let page: PagePart | null = null
    for (const [index, part] of message.parts.entries()) {
      const key = `${message.id}-${index}`
      switch (part.type) {
        case 'page':
          page = part
          break
        case 'user_text':
          blocks.push({ kind: 'user', key, text: part.text, page })
          break
        case 'model_text':
          reply(key).items.push({ kind: 'text', key, text: part.text })
          break
        case 'tool_call': {
          const line: Extract<Item, { kind: 'tool' }> = {
            kind: 'tool',
            key,
            callId: part.id,
            messageId: null,
            name: part.name,
            state: 'running',
            reason: '',
            detail: '',
            output: null,
            undone: null,
          }
          tools.set(part.id, line)
          reply(key).items.push(line)
          break
        }
        case 'tool_result': {
          const line = tools.get(part.call_id)
          if (!line) break
          Object.assign(line, finished(part.outcome, part.result_type, part.result))
          line.messageId = message.id
          results.set(`${message.id}:${part.call_id}`, line)
          break
        }
        case 'notice':
          reply(key).items.push({ kind: 'notice', key, notice: part })
          break
        case 'undone': {
          // 撤銷那一則在後面：那一張卡改成已撤銷，不另畫一塊（M5 票 11）。
          const line = results.get(`${part.message_id}:${part.call_id}`)
          if (line) line.undone = { type: part.result_type, result: part.result }
          break
        }
      }
    }
  }

  if (pending) {
    blocks.push({ kind: 'user', key: 'pending-user', text: pending.text, page: null })
    blocks.push({ kind: 'assistant', key: 'pending-reply', items: pending.items, busy: true })
  }
  return blocks
}

/** 一個工具跑完了：狀態、拒絕的理由碼與結果。 */
function finished(
  outcome: ToolOutcome,
  type: string,
  result: Record<string, unknown>,
): Pick<Extract<Item, { kind: 'tool' }>, 'state' | 'reason' | 'detail' | 'output'> {
  const refused = outcome === 'refused'
  return {
    state: refused ? 'refused' : outcome === 'proposed' ? 'proposed' : 'done',
    reason: refused ? reasonOf(result) : '',
    detail: refused && typeof result.detail === 'string' ? result.detail : '',
    output: { type, result },
  }
}

/** `Refusal.reason`（理由碼）。結果不是那個形狀時是空字串。 */
function reasonOf(result: Record<string, unknown>): string {
  return typeof result.reason === 'string' ? result.reason : ''
}

/** 串流到的一個 chunk 併進正在畫的那一段。`start` 與 `finish` 由呼叫端處理。 */
export function withChunk(items: Item[], chunk: Chunk): Item[] {
  switch (chunk.type) {
    case 'text-delta': {
      const last = items.at(-1)
      if (last?.kind === 'text') {
        return [...items.slice(0, -1), { ...last, text: last.text + chunk.delta }]
      }
      return [...items, { kind: 'text', key: `pending-${items.length}`, text: chunk.delta }]
    }
    case 'tool-input-start':
      return [
        ...items,
        {
          kind: 'tool',
          // 同一則回覆裡同一個 id 可能出現兩次（本機模型每一輪都用 `call_0`）：key 照位置，不照 id。
          key: `pending-${items.length}-${chunk.tool_call_id}`,
          callId: chunk.tool_call_id,
          messageId: null,
          name: chunk.tool_name,
          state: 'running',
          reason: '',
          detail: '',
          output: null,
          undone: null,
        },
      ]
    case 'tool-output-available': {
      // 結果接到這個 id 還在跑的最後那一次（同一個 id 先前那一次已經有結果了）。
      const at = items.findLastIndex(
        (item) =>
          item.kind === 'tool' && item.callId === chunk.tool_call_id && item.state === 'running',
      )
      return items.map((item, index) =>
        index === at && item.kind === 'tool'
          ? { ...item, ...finished(chunk.outcome, chunk.result_type, chunk.result) }
          : item,
      )
    }
    case 'notice':
      return [...items, { kind: 'notice', key: `pending-${items.length}`, notice: chunk.notice }]
    default:
      return items
  }
}

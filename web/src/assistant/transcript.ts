import type { Chunk, Message, NoticePart } from '../api/assistant'

/**
 * 存下來的那幾則（加上正在串流的那一段）→ 畫面上的一塊一塊（`.scratch/m5/side-panel-shape.md` §3）。
 *
 * 一句使用者的話一塊；它之後、下一句之前的模型回合、工具結果與 notice 收成同一塊「助理」——
 * 一則訊息之後模型可以來回好幾輪，畫面上仍是它回的那一次。工具的狀態行把呼叫與結果以 call id 接起來：
 * 有呼叫沒結果是「正在查」，結果是 `Refusal` 是「沒做成」。
 */

type ToolState = 'running' | 'done' | 'refused'

export type Item =
  | { kind: 'text'; key: string; text: string }
  | { kind: 'tool'; key: string; name: string; state: ToolState; reason: string }
  | { kind: 'notice'; key: string; notice: NoticePart }

export type Block =
  | { kind: 'user'; key: string; text: string }
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

  const reply = (key: string): Extract<Block, { kind: 'assistant' }> => {
    const last = blocks.at(-1)
    if (last?.kind === 'assistant') return last
    const block = { kind: 'assistant' as const, key, items: [], busy: false }
    blocks.push(block)
    return block
  }

  for (const message of shown) {
    for (const [index, part] of message.parts.entries()) {
      const key = `${message.id}-${index}`
      switch (part.type) {
        case 'user_text':
          blocks.push({ kind: 'user', key, text: part.text })
          break
        case 'model_text':
          reply(key).items.push({ kind: 'text', key, text: part.text })
          break
        case 'tool_call': {
          const line = {
            kind: 'tool' as const,
            key,
            name: part.name,
            state: 'running' as const,
            reason: '',
          }
          tools.set(part.id, line)
          reply(key).items.push(line)
          break
        }
        case 'tool_result': {
          const line = tools.get(part.call_id)
          if (!line) break
          const refused = part.outcome === 'refused'
          line.state = refused ? 'refused' : 'done'
          line.reason = refused ? reasonOf(part.result) : ''
          break
        }
        case 'notice':
          reply(key).items.push({ kind: 'notice', key, notice: part })
          break
      }
    }
  }

  if (pending) {
    blocks.push({ kind: 'user', key: 'pending-user', text: pending.text })
    blocks.push({ kind: 'assistant', key: 'pending-reply', items: pending.items, busy: true })
  }
  return blocks
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
          key: `pending-${chunk.tool_call_id}`,
          name: chunk.tool_name,
          state: 'running',
          reason: '',
        },
      ]
    case 'tool-output-available':
      return items.map((item) =>
        item.kind === 'tool' && item.key === `pending-${chunk.tool_call_id}`
          ? { ...item, state: chunk.outcome === 'refused' ? 'refused' : 'done' }
          : item,
      )
    case 'notice':
      return [...items, { kind: 'notice', key: `pending-${items.length}`, notice: chunk.notice }]
    default:
      return items
  }
}

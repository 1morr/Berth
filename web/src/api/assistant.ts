import { queryOptions } from '@tanstack/react-query'
import { EventSourceParserStream } from 'eventsource-parser/stream'

import { apiGet, apiPost, apiStream } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * 助理的對話（M5 票 08，`.scratch/m5/side-panel-shape.md`）。
 *
 * **送一句話是 POST、回應本身就是 SSE**（照 Vercel AI SDK 的 UI message stream）：一行 `data:` 一個帶
 * `type` 的 chunk，`start` → `text-delta` / `tool-input-start` / `tool-output-available` / `notice` →
 * `finish`。`EventSource` 送不了 POST，所以用 fetch 讀、`eventsource-parser` 切行。這條串流只屬於這一個
 * 請求，與 `/events/stream` 那個全體廣播無關。
 *
 * 串流的字是先畫上去的：**真相在資料庫**，`finish` 之後重讀這則對話（`conversationQueryOptions`）。
 */

export type AssistantStatus = Schemas['AssistantStatusOut']

export type ConversationSummary = Schemas['ConversationSummaryOut']

export type Conversation = Schemas['ConversationOut']

export type Message = Schemas['MessageOut']

export type NoticePart = Schemas['NoticePart']

export type Chunk = Schemas['AssistantChunk']

export type AssistantRefusal = Schemas['AssistantRefusal']

/** 登錄表自己的拒絕理由（後端 `services/registry.ToolRefusal`）。 */
export type ToolRefusal = Schemas['ToolRefusal']

/**
 * 結果卡（M5 票 09）：工具結果的 `result_type` 是哪一種、那一種的 `result` 長什麼樣。
 * 名字的封閉集合由後端從命令登錄表產生（`ToolResultType`），每一種的形狀是同名的 component。
 * 存下的 `ToolResultPart.result_type` 只是字串：舊版本存下、這一版已經拿掉的型別認不得。
 */
export type ToolResultType = Schemas['ToolResultType']

export type ToolOutcome = Schemas['ToolOutcome']

export type ToolResults = { [K in ToolResultType]: Schemas[K] }

export type RecentImports = Schemas['RecentImports']

export type RecentWork = Schemas['RecentWork']

/**
 * 確認卡（M5 票 10，CONTEXT.md 的 Proposal）：不可逆的工具不執行，變成一張等人按的卡。工具結果裡存的是提出
 * 時的那一份；按過之後的狀態與結果在 `Conversation.proposals`（同形）。
 */
export type ProposalCard = Schemas['ProposalCard']

/** 卡上「會發生什麼」的型別名（後端從要人按的那幾個工具產生），每一種的形狀是同名的 component。 */
export type ProposalPreviewType = Schemas['ProposalPreviewType']

export type ProposalPreviews = { [K in ProposalPreviewType]: Schemas[K] }

export type IndexerAddition = Schemas['IndexerAddition']

export type DownloadsDeletion = Schemas['DownloadsDeletion']

export type ProposalRefusal = Schemas['ProposalRefusal']

/** 回覆的語言（後端的 `Language`）。 */
export type ReplyLanguage = Schemas['MessageIn']['language']

const REASONS: ReasonSet<AssistantRefusal> = {
  not_ready: true,
  conversation_missing: true,
  busy: true,
  empty_message: true,
}

const CHUNK_TYPES: ReasonSet<Chunk['type']> = {
  start: true,
  'text-delta': true,
  'tool-input-start': true,
  'tool-output-available': true,
  notice: true,
  finish: true,
}

const PROPOSAL_REASONS: ReasonSet<ProposalRefusal> = {
  proposal_missing: true,
  already_decided: true,
}

/** 按卡片被拒的理由：卡片的（不是你的、已經按過）或對話的（回覆還在跑）。認不得的是 `null`。 */
export function proposalRefusalOf(
  error: unknown,
): Refusal<ProposalRefusal> | Refusal<AssistantRefusal> | null {
  return parseRefusal(error, PROPOSAL_REASONS) ?? parseRefusal(error, REASONS)
}

/** 按確認：以按的這個人執行。按下去的當下不成立的，回來的卡是 `expired`、理由在 `result`。 */
export function confirmProposal(id: number): Promise<ProposalCard> {
  return apiPost<ProposalCard>(`/proposals/${id}/confirm`)
}

/** 按拒絕：記下來，什麼都不做。 */
export function rejectProposal(id: number): Promise<ProposalCard> {
  return apiPost<ProposalCard>(`/proposals/${id}/reject`)
}

/** 認不得的理由是 `null`，畫面照請求為什麼沒成說。 */
export function assistantRefusalOf(error: unknown): Refusal<AssistantRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const assistantStatusQueryOptions = queryOptions({
  queryKey: ['assistant'],
  queryFn: ({ signal }) => apiGet<AssistantStatus>('/assistant', { signal }),
})

export const CONVERSATIONS_KEY = ['conversations'] as const

export const conversationsQueryOptions = queryOptions({
  queryKey: CONVERSATIONS_KEY,
  queryFn: ({ signal }) => apiGet<ConversationSummary[]>('/conversations', { signal }),
})

/** 回覆還在後端跑時每隔一下重讀（送出它的那一條串流斷了：關過面板、換過頁）。 */
const REPLYING_POLL_MS = 1500

export function conversationQueryOptions(id: number) {
  return queryOptions({
    queryKey: [...CONVERSATIONS_KEY, id],
    queryFn: ({ signal }) => apiGet<Conversation>(`/conversations/${id}`, { signal }),
    refetchInterval: (query) => (query.state.data?.replying ? REPLYING_POLL_MS : false),
  })
}

/**
 * 送一句話，把每一個 chunk 交給 `onChunk`，讀到 `finish`（或串流結束）為止。`conversationId` 是 `null`
 * 時開一則新的（id 在 `start` 那一個）。後端拒絕是 `ApiError`（`assistantRefusalOf` 讀得出理由）；
 * 串流中途斷了是那個讀取錯誤——回覆在後端照樣跑完。
 */
export async function sendMessage({
  conversationId,
  text,
  language,
  onChunk,
  signal,
}: {
  conversationId: number | null
  text: string
  language: ReplyLanguage
  onChunk: (chunk: Chunk) => void
  signal?: AbortSignal
}): Promise<void> {
  const path =
    conversationId === null ? '/conversations' : `/conversations/${conversationId}/messages`
  const response = await apiStream(path, { text, language } satisfies Schemas['MessageIn'], signal)
  if (!response.body) return
  const reader = response.body
    .pipeThrough(new TextDecoderStream())
    .pipeThrough(new EventSourceParserStream())
    .getReader()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) return
    const chunk = chunkOf(value.data)
    if (chunk === null) continue
    onChunk(chunk)
    if (chunk.type === 'finish') {
      await reader.cancel()
      return
    }
  }
}

/** 認得出形狀才交出去；後端多了一種 chunk 時略過它，不讓整段回覆炸掉。 */
function chunkOf(data: string): Chunk | null {
  try {
    const parsed: unknown = JSON.parse(data)
    if (typeof parsed !== 'object' || parsed === null) return null
    const type = (parsed as { type?: unknown }).type
    return typeof type === 'string' && Object.hasOwn(CHUNK_TYPES, type) ? (parsed as Chunk) : null
  } catch {
    return null
  }
}

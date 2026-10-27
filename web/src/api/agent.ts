import { queryOptions } from '@tanstack/react-query'
import { DefaultChatTransport, type UIMessage } from 'ai'

import { apiGet, apiPost, CSRF_HEADERS, responseError } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * 側面板的助理（M5 票 11、12，plan §6〈agent〉）。
 *
 * **歷史由伺服器保管**：`useChat` 每次送整份訊息，後端只取最後一則使用者訊息的字（brief §20.24），
 * 所以這裡只送那一則；重新載入時從 `GET /agent/conversations/{id}` 接回來。
 */

export type AgentStatus = Schemas['AgentStatusOut']

export type AgentRefusal = Schemas['AgentRefusal']

const REASONS: ReasonSet<AgentRefusal> = {
  ai_disabled: true,
  ai_paused: true,
  busy: true,
  no_message: true,
  conversation_missing: true,
  not_continuable: true,
  unknown_command: true,
  slash_command: true,
}

export function agentRefusalOf(error: unknown): Refusal<AgentRefusal> | null {
  return parseRefusal(error, REASONS)
}

/**
 * AI 開著沒有、provider 暫停到什麼時候（票 20；管理員另有 `pause_error`）。登入就讀得到；關著時面板
 * 只說怎麼設定（管理員）或「管理員還沒設定」。暫停的畫法在票 22。
 */
export const agentStatusQueryOptions = queryOptions({
  queryKey: ['agent', 'status'],
  queryFn: ({ signal }) => apiGet<AgentStatus>('/agent/status', { signal }),
})

/**
 * 一段對話存著的訊息（`useChat` 的 `UIMessage`）。沒有這段（第一次用、換了帳號、被清掉）是 `null`：
 * 面板就從空的開始，不當成錯誤。
 */
export async function readConversation(
  id: string,
  signal?: AbortSignal,
): Promise<UIMessage[] | null> {
  try {
    const found = await apiGet<Schemas['ConversationOut']>(
      `/agent/conversations/${encodeURIComponent(id)}`,
      { signal },
    )
    // 形狀由後端的 pydantic-ai `dump_messages(sdk_version=7)` 決定，就是 ai 7 的 `UIMessage`。
    return found.messages as unknown as UIMessage[]
  } catch (error) {
    if (agentRefusalOf(error)?.reason === 'conversation_missing') return null
    throw error
  }
}

/**
 * `useChat` 的傳輸：只送最後一則（plan §11.6〈串流〉），帶介面語言（停下來的說明照它寫），
 * 失敗時丟出與其餘 API 同一種 `ApiError`——畫面才分得出 `busy` 與 `ai_disabled`。
 */
export function agentTransport(language: () => string) {
  return new DefaultChatTransport<UIMessage>({
    api: '/api/agent/chat',
    headers: CSRF_HEADERS,
    prepareSendMessagesRequest: ({ id, messages, trigger, messageId }) => ({
      body: {
        id,
        trigger,
        messageId,
        messages: messages.slice(-1),
        language: language(),
      },
    }),
    fetch: async (input, init) => {
      const response = await fetch(input, init)
      if (!response.ok) throw await responseError('POST', '/agent/chat', response)
      return response
    },
  })
}

/**
 * 斜線指令的結果（M5 票 18，`services/slash.py`）：照 `command` 分。字由畫面照介面語言組。
 */
export type SlashResult =
  | Schemas['NewOut']
  | Schemas['CompactOut']
  | Schemas['UsageOut']
  | Schemas['StatusOut']
  | Schemas['PendingOut']
  | Schemas['SkillsOut']

export type SlashName = SlashResult['command']

/** 提示清單的順序；少一個或多一個都是編譯錯誤（同 `REASONS`）。 */
const SLASH: Record<SlashName, true> = {
  new: true,
  compact: true,
  usage: true,
  status: true,
  pending: true,
  skills: true,
}

const SLASH_COMMANDS = Object.keys(SLASH) as SlashName[]

/** 以 `/` 開頭的就是指令，不送給模型（後端也擋：`slash_command`）。 */
export function isSlashCommand(text: string): boolean {
  return text.trimStart().startsWith('/')
}

/** 打到一半的指令（`/`、`/co`）：提示清單只在這時候出現。 */
export function slashMatches(draft: string): SlashName[] {
  const typed = /^\/([a-z]*)$/.exec(draft)
  if (typed === null) return []
  return SLASH_COMMANDS.filter((name) => name.startsWith(typed[1]))
}

export function runSlashCommand(conversationId: string, text: string): Promise<SlashResult> {
  return apiPost<SlashResult>(
    `/agent/conversations/${encodeURIComponent(conversationId)}/commands`,
    { text },
  )
}

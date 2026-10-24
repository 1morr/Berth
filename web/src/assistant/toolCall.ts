import { createContext } from 'react'

import type { ToolOutput } from './transcript'

/**
 * 一張結果卡是哪一次工具呼叫畫的（M5 票 11）：卡上的撤銷鍵指著它。`ItemView` 給、`UndoButton` 與卡片讀；
 * 與元件分檔是 fast refresh 的要求。
 */
export interface ToolCall {
  callId: string
  /** 存著結果的那一則；還在串流是 `null`（存下來之前不給撤銷）。 */
  messageId: number | null
  /** 這個人按得到這個工具的撤銷（後端 `GET /assistant` 的 `tools[].undoable`，照撤銷那支端點的門禁）。 */
  undoable: boolean
  /** 有人撤銷過了：撤掉了什麼。沒撤銷是 `null`。 */
  undone: ToolOutput | null
}

export const ToolCallContext = createContext<ToolCall>({
  callId: '',
  messageId: null,
  undoable: false,
  undone: null,
})

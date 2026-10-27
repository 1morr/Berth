import { createContext, useContext } from 'react'

import type { Proposal } from '../api/proposals'

/**
 * 卡片按下去之後要對話做的事（M5 票 13）：卡片在對話紀錄深處，`useChat` 在 `Chatting` 那一層。
 *
 * `respond`：卡片還是最後一則助理訊息裡等確認的那一格時，告訴 `useChat` 按了什麼，所有等確認的都
 * 有回應了就送出恢復的那一則（伺服器照 Proposal 決定，前端的核准只是觸發）。脫離過的卡片不送：
 * 對話已經往下走了，下一則訊息會把結果帶給模型。
 */
export interface CardActions {
  respond: (toolCallId: string, decided: Proposal) => Promise<void>
}

export const CardContext = createContext<CardActions | null>(null)

export function useCardActions(): CardActions {
  const actions = useContext(CardContext)
  if (actions === null) throw new Error('useCardActions outside <Chatting>')
  return actions
}

import { createContext } from 'react'

import type { ProposalCard } from '../api/assistant'

/**
 * 一則對話裡確認卡的現況（M5 票 10）：卡片從存下的工具結果畫，狀態與結果讀這一份。`Chat` 給、`ProposalCard`
 * 與撤銷鍵（票 11）讀；與元件分檔是 fast refresh 的要求（一個檔案只匯出元件）。
 */
export interface Proposals {
  /** 畫面上這則對話；還沒有對話是 `null`。結果卡上的撤銷指著它（M5 票 11）。 */
  conversationId: number | null
  /** 這則對話每一張卡的現況，以 id 查。 */
  cards: ReadonlyMap<number, ProposalCard>
  /** 回覆還在跑：按卡片要等它講完（後端那時回 `busy`）。 */
  replying: boolean
  /** 按過之後重讀這則對話。 */
  refresh: () => Promise<void>
}

export const ProposalsContext = createContext<Proposals>({
  conversationId: null,
  cards: new Map(),
  replying: false,
  refresh: () => Promise.resolve(),
})

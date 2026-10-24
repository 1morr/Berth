import { createContext } from 'react'

/**
 * 側面板對頁面開的門（M5 票 14）：AI 活動頁的「出自《對話》」要打開面板並顯示那一則。面板的開關與
 * 選取的對話都在 `AppShell` / `AssistantPanel` 裡，頁面只能提出請求。與元件分檔是 fast refresh 的要求。
 */
export interface AssistantControl {
  openConversation: (id: number) => void
}

export const AssistantControlContext = createContext<AssistantControl>({
  openConversation: () => undefined,
})

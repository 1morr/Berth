import { createContext, useContext } from 'react'

/**
 * 側面板開著沒有、目前是哪一段對話（M5 票 12，`.scratch/m5/side-panel-shape.md`）。
 *
 * **放在根路由而不是 `AppShell`**：每一頁各自包一層 `AppShell`，換頁時它整個重掛；面板的開關、
 * 對話與還在串流的那一輪要撐過換頁。
 */
export interface PanelState {
  open: boolean
  setOpen: (open: boolean) => void
  conversationId: string
  /**
   * 「新對話」：換一個 id；舊的那段還在伺服器上，只是這張票沒有清單可以回去。`lost` 是伺服器說這段
   * 對話不在了（換了帳號、被清掉），新的那段開頭要說一句為什麼換了。
   */
  startNew: (lost?: boolean) => void
  /** 新的這段是因為舊的不見了才開的。 */
  restarted: boolean
  /** 還沒送出的字。放在這一層：換頁、送不出去換了一段新對話，都還在。 */
  draft: string
  setDraft: (draft: string) => void
}

/** 頁首那顆「助理」鍵：面板收起時焦點回到它。 */
export const TOGGLE_ID = 'agent-toggle'
/** 面板本身（`aria-controls`）、它的標題與輸入欄：打開時焦點落在輸入欄，還沒有就落在標題。 */
export const PANEL_ID = 'agent-panel'
export const PANEL_TITLE_ID = 'agent-panel-title'
export const INPUT_ID = 'agent-input'
/** 斜線指令的提示清單（M5 票 18）與它的一列：輸入欄的 `aria-activedescendant` 指著那一列。 */
export const SLASH_HINT_ID = 'agent-slash-hint'

export function slashOptionId(name: string): string {
  return `${SLASH_HINT_ID}-${name}`
}

export const PanelContext = createContext<PanelState | null>(null)

export function usePanel(): PanelState {
  const state = useContext(PanelContext)
  if (state === null) throw new Error('usePanel outside <AgentProvider>')
  return state
}

const OPEN_KEY = 'berth.agent.open'
const CONVERSATION_KEY = 'berth.agent.conversation'

/** 開關記在這個分頁（`sessionStorage`）：換頁、重新載入都照舊，另開一個分頁是關著的。 */
export function readOpen(): boolean {
  try {
    return sessionStorage.getItem(OPEN_KEY) === '1'
  } catch {
    return false
  }
}

export function writeOpen(open: boolean): void {
  try {
    sessionStorage.setItem(OPEN_KEY, open ? '1' : '0')
  } catch {
    // 私密視窗或封鎖了網站資料：面板照常開關，只是不記。
  }
}

/** 對話 id 記在這個瀏覽器（`localStorage`）：重新載入、另開分頁都接得回同一段。 */
export function readConversationId(): string {
  try {
    const stored = localStorage.getItem(CONVERSATION_KEY)
    if (stored !== null && CONVERSATION_ID.test(stored)) return stored
  } catch {
    // 同上：讀不到就開一段新的。
  }
  return rememberNewConversation()
}

export function rememberNewConversation(): string {
  const id = crypto.randomUUID()
  try {
    localStorage.setItem(CONVERSATION_KEY, id)
  } catch {
    // 同上。
  }
  return id
}

/** 後端收的形狀（`services/agent.CONVERSATION_ID`）。 */
const CONVERSATION_ID = /^[A-Za-z0-9_-]{1,64}$/

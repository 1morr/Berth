/**
 * 側面板的寬度（M5.6 票 10b）：桌面拖面板左緣的把手、或把把手聚焦後按左右方向鍵。單位是 rem，
 * 與版面節奏同一把尺（DESIGN.md〈節奏〉）。
 *
 * 上下限照 DESIGN.md〈側面板〉的版面：`26rem` 是原本的一欄；`24rem`（384px）挨著 390 的手機寬
 * （24.4rem）——票 10 量到那裡 Route 下拉 330px 加左右各 1rem 內距是 362px，再窄就換這張卡擠；
 * `40rem` 是 1280 開著面板時頁面還剩得下兩欄（e2e 也在 `lg` 的 1024 量過沒有橫向捲動）。
 * 夾在範圍裡，不是自由數字。
 */
export const PANEL_WIDTH_DEFAULT = 26
export const PANEL_WIDTH_MIN = 24
export const PANEL_WIDTH_MAX = 40
/** 左右方向鍵一次一步；`Shift` 一起按是加大步進。 */
export const PANEL_WIDTH_STEP = 1
export const PANEL_WIDTH_LARGE_STEP = 4

/** 每人每台裝置的顯示偏好，記在這個瀏覽器，不上伺服器（理由在票 10b 的 Comments）。 */
const WIDTH_KEY = 'berth.agent.width'

/** 夾回上下限；小數留一位，拖動時不會累積成一串浮點誤差。壞掉的值回到預設。 */
export function clampPanelWidth(width: number): number {
  if (!Number.isFinite(width)) return PANEL_WIDTH_DEFAULT
  const clamped = Math.min(Math.max(width, PANEL_WIDTH_MIN), PANEL_WIDTH_MAX)
  return Math.round(clamped * 10) / 10
}

/** 頁面的根字級：拖動是 px，寬度是 rem，兩者靠它換算。量不到時當 16（jsdom、還沒套樣式時）。 */
export function rootRem(): number {
  const size = Number.parseFloat(getComputedStyle(document.documentElement).fontSize)
  return Number.isFinite(size) && size > 0 ? size : 16
}

/** 這個瀏覽器上次拖到的寬度；沒記、記壞了都是預設。 */
export function readPanelWidth(): number {
  try {
    const raw = localStorage.getItem(WIDTH_KEY)
    if (raw === null || raw.trim() === '') return PANEL_WIDTH_DEFAULT
    const stored = Number(raw)
    return Number.isFinite(stored) ? clampPanelWidth(stored) : PANEL_WIDTH_DEFAULT
  } catch {
    return PANEL_WIDTH_DEFAULT
  }
}

export function writePanelWidth(width: number): void {
  try {
    localStorage.setItem(WIDTH_KEY, String(clampPanelWidth(width)))
  } catch {
    // 私密視窗或封鎖了網站資料：拖動照常，只是不記。
  }
}

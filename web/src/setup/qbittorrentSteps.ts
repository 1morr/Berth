import type { QbittorrentStep } from '../api/setup'

/**
 * 頁 2 的纜繩：只有 WebUI 登入那一條（plan §9.3、§8.1）。Berth 不寫全域偏好（M4 票 32）。
 *
 * **纜繩的 key 就是 `app/setPreferences` 的鍵名**：畫面顯示的與 Berth 送出去的是同一個字串。
 */
export const STEP_LABEL = {
  web_ui_password: 'qbittorrent.step.web_ui_password',
} as const satisfies Record<QbittorrentStep, string>

/** 每一條在 qBittorrent 介面上的位置，失敗時使用者要自己去按的就是那裡。 */
export const STEP_FIX = {
  web_ui_password: 'qbittorrent.fix.web_ui_password',
} as const satisfies Record<QbittorrentStep, string>

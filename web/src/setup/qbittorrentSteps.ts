import type { QbittorrentStep } from '../api/setup'

/**
 * 第 4 步的五個鍵加一條密碼（plan §9.3 第 4 步、§8.1）。
 *
 * **纜繩的名字就是 `app/setPreferences` 的鍵名**：畫面顯示的與 Berth 送出去的是同一個字串，
 * 使用者在 qBittorrent 自己的介面上也找得到它（剖面即預覽）。
 */
export const STEP_LABEL = {
  temp_path_enabled: 'qbittorrent.step.temp_path_enabled',
  temp_path: 'qbittorrent.step.temp_path',
  save_path: 'qbittorrent.step.save_path',
  auto_tmm_enabled: 'qbittorrent.step.auto_tmm_enabled',
  category_changed_tmm_enabled: 'qbittorrent.step.category_changed_tmm_enabled',
  web_ui_password: 'qbittorrent.step.web_ui_password',
} as const satisfies Record<QbittorrentStep, string>

/** 每一條在 qBittorrent 介面上的位置，失敗時使用者要自己去按的就是那裡。 */
export const STEP_FIX = {
  temp_path_enabled: 'qbittorrent.fix.temp_path_enabled',
  temp_path: 'qbittorrent.fix.temp_path',
  save_path: 'qbittorrent.fix.save_path',
  auto_tmm_enabled: 'qbittorrent.fix.auto_tmm_enabled',
  category_changed_tmm_enabled: 'qbittorrent.fix.category_changed_tmm_enabled',
  web_ui_password: 'qbittorrent.fix.web_ui_password',
} as const satisfies Record<QbittorrentStep, string>

import type { JellyfinWeb } from '../api/inventory'

/** 瀏覽器現在在哪裡。只取組網址要的兩格，測試才不必偽造整個 `Location`。 */
export interface BrowserLocation {
  protocol: string
  hostname: string
}

/**
 * Jellyfin 某個項目的詳細頁（brief §12、§20.1）。播放一律交給 Jellyfin，Berth 只給這一條。
 *
 * 形狀用 Jellyfin 客戶端自己產生的 `#/details?id=`（不帶 `!`，M0 票 04 實測）。**不帶
 * `serverId`**：2026-09-15 對 12.0.0 實測不帶也開到同一頁，而帶它就得多存一個值。
 *
 * 主機的推導在後端（`services/deeplink.py`），**只有最後一步在這裡**：套件內的 Jellyfin
 * 開在瀏覽器現在的主機名上，而那個名字只有瀏覽器知道。還沒找到 item、或兩者都不知道時回
 * `null`——畫面說原因，不給一條點了會 404 的死連結（票 13 驗收）。
 */
export function jellyfinDetailsUrl(
  web: JellyfinWeb,
  itemId: string,
  here: BrowserLocation,
): string | null {
  if (!itemId) return null
  const base =
    web.url || (web.port === null ? '' : `${here.protocol}//${here.hostname}:${web.port}`)
  if (!base) return null
  return `${base}/web/#/details?id=${encodeURIComponent(itemId)}`
}

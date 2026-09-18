import type { JellyfinWeb } from '../api/jellyfin'

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
  const base = jellyfinBase(web, here)
  if (!base) return null
  return `${base}/web/#/details?id=${encodeURIComponent(itemId)}`
}

/**
 * Jellyfin 的媒體庫設定頁（票 14a）：新增 Route 時媒體庫沒有空路徑，下一步是在那裡替它加一條。
 * 推不出主機時回 `null`，畫面只留文字。
 */
export function jellyfinLibrariesUrl(web: JellyfinWeb, here: BrowserLocation): string | null {
  const base = jellyfinBase(web, here)
  return base ? `${base}/web/#/dashboard/libraries` : null
}

/**
 * 瀏覽器開 Jellyfin 網頁用的主機。深連結與媒體庫設定頁的連結共用這一份推導；兩者都不知道時回 `null`。
 * Jellyfin 網頁的路由形狀（`/web/#/…`）只寫在這個檔案裡。
 */
export function jellyfinBase(web: JellyfinWeb, here: BrowserLocation): string | null {
  const base =
    web.url || (web.port === null ? '' : `${here.protocol}//${here.hostname}:${web.port}`)
  return base || null
}

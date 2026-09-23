import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { HealthDetail } from './health'
import type { JellyfinWeb } from './jellyfin'
import type { QbittorrentSetup, Schemas, ServiceKind } from './schemas'

/**
 * 服務設定頁（`/settings/services`，只有 admin）。
 *
 * 這一頁是**維運動作**，不是連線表單：位址與憑證仍然在精靈裡改（精靈跑完之後它就是設定
 * 入口，plan §6），所以這裡沒有 `PUT`。對外網址與磁碟空間門檻兩個欄位不是連線資訊，住在這裡。
 */

/** 與健康頁同一份形狀——同一件事不該有兩種說法。 */
export const servicesQueryOptions = queryOptions({
  queryKey: ['settings', 'services'],
  queryFn: () => apiGet<HealthDetail>('/settings/services'),
})

/** 「測試連線」：只重測這一個服務，其餘的結果留著。 */
export function testService(kind: ServiceKind): Promise<HealthDetail> {
  return apiPost<HealthDetail>(`/settings/services/${kind}/test`)
}

/** 現值與建議值的逐鍵差異。連得到才有內容（brief §16.3）。 */
export const qbittorrentDriftQueryOptions = queryOptions({
  queryKey: ['settings', 'qbittorrent'],
  queryFn: () => apiGet<QbittorrentSetup>('/settings/qbittorrent/diff'),
})

/** 「還原建議設定」。只寫有差異的鍵，跑的是精靈第 4 步的同一支命令。 */
export function restoreQbittorrent(): Promise<QbittorrentSetup> {
  return apiPost<QbittorrentSetup>('/settings/qbittorrent/apply')
}

/**
 * Jellyfin 的對外網址，與它沒填時推導出來的樣子（票 13）。
 *
 * 它是這一頁唯一的「表單」，但不是連線資訊：精靈用不到它，填錯也不會讓任何服務斷線——
 * 它只決定媒體庫上那一條深連結開在哪台主機。
 */
export const jellyfinAddressQueryOptions = queryOptions({
  queryKey: ['settings', 'jellyfin'],
  queryFn: () => apiGet<JellyfinWeb>('/settings/jellyfin'),
})

/** 存下對外網址。空白就是清掉，回到推導。不是 http(s) 的位址回 422。 */
export function saveJellyfinAddress(publicUrl: string): Promise<JellyfinWeb> {
  return apiPost<JellyfinWeb>('/settings/jellyfin', {
    public_url: publicUrl,
  } satisfies Schemas['JellyfinAddressIn'])
}

/** 磁碟空間門檻（GB，M2 票 09c）。`0` 是不量。 */
export const diskQueryOptions = queryOptions({
  queryKey: ['settings', 'disk'],
  queryFn: () => apiGet<Schemas['DiskOut']>('/settings/disk'),
})

/** 存下門檻。後端存完立刻重量一次，所以待處理清單也要重問。負數回 422。 */
export function saveDisk(minFreeGb: number): Promise<Schemas['DiskOut']> {
  return apiPost<Schemas['DiskOut']>('/settings/disk', {
    min_free_gb: minFreeGb,
  } satisfies Schemas['DiskIn'])
}

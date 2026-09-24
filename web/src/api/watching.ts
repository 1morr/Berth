import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import { retryUnlessRefused } from './jellyfin'
import type { Schemas } from './schemas'

/**
 * 繼續觀看與下一集（`berth/services/watching.py`、M1.5 票 07）：媒體庫頁上方，只含那個媒體庫的。資料原樣來自
 * Jellyfin，前端不送任何使用者 id。首頁那一份（整個帳號）隨探索頁只放 TMDB 牆拿掉了（M3 票 06）。
 */

/** 兩列與深連結的主機。 */
export type Watching = Schemas['WatchingOut']

/** 一列上的一格：一集或一部電影。 */
export type WatchingCard = Schemas['WatchingCardOut']

/** 只含這個媒體庫的。媒體庫 id 由後端對允許清單驗過才轉給 Jellyfin。 */
export function libraryWatchingQueryOptions(libraryId: string) {
  return queryOptions({
    queryKey: ['watching', 'library', libraryId],
    queryFn: () => apiGet<Watching>(`/inventory/${encodeURIComponent(libraryId)}/watching`),
    retry: retryUnlessRefused,
  })
}

import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import { retryUnlessRefused } from './jellyfin'
import type { Schemas } from './schemas'

/**
 * 繼續觀看與下一集（`berth/services/watching.py`、M1.5 票 07）：首頁上方是這個人整個帳號的，媒體庫頁上方
 * 只含那個媒體庫的。資料原樣來自 Jellyfin，前端不送任何使用者 id。
 */

/** 兩列與深連結的主機。 */
export type Watching = Schemas['WatchingOut']

/** 一列上的一格：一集或一部電影。 */
export type WatchingCard = Schemas['WatchingCardOut']

/** 首頁：整個帳號。後端不帶媒體庫去問 Jellyfin，它才照這個人的權限限縮。 */
export const homeWatchingQueryOptions = queryOptions({
  queryKey: ['watching', 'home'],
  queryFn: () => apiGet<Watching>('/jellyfin/watching'),
  retry: retryUnlessRefused,
})

/** 媒體庫頁：只含這個媒體庫的。媒體庫 id 由後端對允許清單驗過才轉給 Jellyfin。 */
export function libraryWatchingQueryOptions(libraryId: string) {
  return queryOptions({
    queryKey: ['watching', 'library', libraryId],
    queryFn: () => apiGet<Watching>(`/inventory/${encodeURIComponent(libraryId)}/watching`),
    retry: retryUnlessRefused,
  })
}

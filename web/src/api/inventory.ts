import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/**
 * 媒體庫（`berth/api/inventory.py`、票 13）。
 *
 * 後端叫 inventory、畫面叫「媒體庫」：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端
 * 的媒體庫，而這一頁盤點的是 Library Route。
 */

/** 切換列上的一條 Route，與兩個篩選的數字。 */
export type InventoryRoute = Schemas['InventoryRouteOut']

/** 一條 Route 的整面牆。 */
export type Inventory = Schemas['InventoryOut']

/** 牆上的一格。狀態、計數與 Jellyfin 那一行的判定全部在後端。 */
export type InventoryItem = Schemas['InventoryItemOut']

/** 深連結開在哪一台主機上。媒體庫與設定頁共用。 */
export type JellyfinWeb = Schemas['JellyfinWebOut']

export const inventoriesQueryOptions = queryOptions({
  queryKey: ['inventory'],
  queryFn: () => apiGet<InventoryRoute[]>('/inventory'),
})

export function inventoryQueryOptions(slug: string) {
  return queryOptions({
    queryKey: ['inventory', slug],
    queryFn: () => apiGet<Inventory>(`/inventory/${encodeURIComponent(slug)}`),
  })
}

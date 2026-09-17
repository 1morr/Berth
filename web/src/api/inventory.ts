import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiDelete, apiGet, apiPost } from './client'
import type { Schemas } from './schemas'

/**
 * 媒體庫（`berth/api/inventory.py`、票 13、M1.5 票 03）。
 *
 * 後端叫 inventory、畫面叫「媒體庫」：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
 * 媒體庫。一個 Jellyfin 媒體庫一頁；這位使用者看得到哪幾個由後端的權限閘門決定，前端不知道他的
 * Jellyfin id，也不送任何 id。
 */

/** 這位使用者看得到、Berth 瀏覽得了的一個媒體庫。 */
export type InventoryLibrary = Schemas['InventoryLibraryOut']

/** 一個媒體庫的一頁牆，加上 Berth 經手的每一部。 */
export type Inventory = Schemas['InventoryOut']

/** 牆上的一格。在不在 Jellyfin、連到哪裡、需不需要人的判定全部在後端。 */
export type InventoryCard = Schemas['InventoryCardOut']

/** 深連結開在哪一台主機上。媒體庫與設定頁共用。 */
export type JellyfinWeb = Schemas['JellyfinWebOut']

/** 這位使用者在 Jellyfin 看到哪了（`services/watch.py`、M1.5 票 05）。判定在後端。 */
export type WatchState = Schemas['WatchStateOut']

/**
 * 權限閘門的拒絕（`api/jellyfin.py` 的 `access_refusal`，媒體庫與標記已看共用）：`reason` 挑句子，
 * `detail` 是原文。
 */
export interface AccessRefusal {
  reason: 'account_disabled' | 'library_not_visible' | 'item_not_visible' | 'jellyfin_unreachable'
  detail: string
}

const REASONS: readonly AccessRefusal['reason'][] = [
  'account_disabled',
  'library_not_visible',
  'item_not_visible',
  'jellyfin_unreachable',
]

/**
 * 錯誤是不是媒體庫端點說得出理由的那幾種（與 `refusalOf`、`routeRefusalOf` 同一個形狀）。
 * 後端不可達、或理由不在這份封閉集合裡時是 `null`。
 */
export function accessRefusal(error: unknown): AccessRefusal | null {
  if (!(error instanceof ApiError)) return null
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null) return null
  const reason = (detail as { reason?: unknown }).reason
  if (typeof reason !== 'string' || !REASONS.includes(reason as AccessRefusal['reason'])) {
    return null
  }
  const text = (detail as { detail?: unknown }).detail
  return {
    reason: reason as AccessRefusal['reason'],
    detail: typeof text === 'string' ? text : '',
  }
}

/**
 * 說得出理由的拒絕是答案不是故障，不重試：TanStack Query 預設重試三次、間隔加倍，「找不到這個媒體庫」
 * 會晚七秒才出現，被停用的帳號也要等同樣久才被送回登入頁（票 03 實跑量到）。其餘錯誤照預設。
 */
export function retryUnlessRefused(failures: number, error: Error): boolean {
  return accessRefusal(error) === null && failures < 3
}

export const inventoriesQueryOptions = queryOptions({
  queryKey: ['inventory'],
  queryFn: () => apiGet<InventoryLibrary[]>('/inventory'),
  retry: retryUnlessRefused,
})

/**
 * 標為已看（`POST`）或未看（`DELETE`），回寫入之後的狀態。寫的是 session 那個人的紀錄，前端不送任何
 * 使用者 id。**標為未看復原不了**（觀看次數與時間被清掉，劇集清的是每一集），先確認是畫面的事。
 */
export function markPlayed(itemId: string, played: boolean): Promise<WatchState> {
  const path = `/jellyfin/items/${encodeURIComponent(itemId)}/played`
  return played ? apiPost<WatchState>(path) : apiDelete<WatchState>(path)
}

/**
 * 牆上那一部換成寫入之後的狀態，不重抓整面牆（jellyfin-web 收到 `UserDataChanged` 也是就地改卡片）。
 * 只有 `titles` 有觀看紀錄；`tracked` 一律是 `null`（後端的整份清單不帶它）。
 */
export function withWatch(inventory: Inventory, itemId: string, watch: WatchState): Inventory {
  return {
    ...inventory,
    titles: inventory.titles.map((card) =>
      card.jellyfin_item_id === itemId ? { ...card, watch } : card,
    ),
  }
}

/** 一個媒體庫每一頁的快取鍵都以它開頭：標記已看之後每一頁一起改。 */
export function inventoryKey(libraryId: string) {
  return ['inventory', libraryId] as const
}

/** 牆的排序鍵（Jellyfin `ItemSortBy` 的名字）。每個媒體庫開哪幾個在 `InventoryLibrary.sorts`。 */
export type LibrarySort = Schemas['LibrarySort']

export type SortOrder = Schemas['SortOrder']

/**
 * 牆怎麼排、怎麼篩（M1.5 票 06）：網址上的 `sort`、`order`、`genres`、`years`，對過這個媒體庫的排序選單。
 * **沒寫的就是打開牆時的樣子**（選單第一個、遞增、不篩），網址與快取鍵都少一種寫法。只套在 Jellyfin 那一頁：
 * 還沒進 Jellyfin、待審、Unmatched 是 Berth 的清單，沒有 Jellyfin 的類型可以篩。
 */
export interface WallQuery {
  sort?: LibrarySort
  order?: Extract<SortOrder, 'Descending'>
  genres?: string[]
  years?: number[]
}

/** 網址讀出來、還沒對過排序選單的樣子（`routes.tsx` 的 `validateSearch` 只認得形狀）。 */
export type WallSearch = Omit<WallQuery, 'sort'> & { sort?: string }

/**
 * 把網址上的排序對過這個媒體庫的選單：選單上沒有的（手改的網址、從電影庫抄來的 `DatePlayed`）當成預設，
 * 不送出去——後端會拒絕它，而那只是一個打錯的網址。媒體庫還不知道時也不送。
 */
export function wallQuery(search: WallSearch, library: InventoryLibrary | undefined): WallQuery {
  const query: WallQuery = {}
  const sort = library?.sorts.find((key) => key === search.sort)
  if (sort !== undefined && sort !== library?.sorts[0]) query.sort = sort
  if (search.order) query.order = search.order
  if (search.genres?.length) query.genres = search.genres
  if (search.years?.length) query.years = search.years
  return query
}

/** 有沒有在篩類型或年份。排序不算：它不會讓哪一部作品不見。 */
export function narrowed(query: WallQuery): boolean {
  return Boolean(query.genres?.length || query.years?.length)
}

/**
 * 一頁牆。第 1 頁不帶 `?page=`；類型與年份重複帶（類型名可能含逗號，研究 §3.1）。
 *
 * **換頁、換排序或篩選時先留著上一面牆**：沒有的話牆換成空位格，勾類型的那一格跟著被卸掉，鍵盤使用者的焦點
 * 掉回 `body`。換媒體庫時不留——那是別的媒體庫的東西。
 */
export function inventoryQueryOptions(libraryId: string, page: number, query: WallQuery = {}) {
  const params = new URLSearchParams()
  if (page > 1) params.set('page', String(page))
  if (query.sort) params.set('sort', query.sort)
  if (query.order) params.set('order', query.order)
  for (const genre of query.genres ?? []) params.append('genres', genre)
  for (const year of query.years ?? []) params.append('years', String(year))
  const search = params.size > 0 ? `?${params}` : ''
  return queryOptions({
    queryKey: [...inventoryKey(libraryId), page, query],
    queryFn: () => apiGet<Inventory>(`/inventory/${encodeURIComponent(libraryId)}${search}`),
    retry: retryUnlessRefused,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === libraryId ? previous : undefined,
  })
}

/** 類型與年份篩選的選項：這個媒體庫裡的作品有的那些。 */
export type InventoryFilters = Schemas['InventoryFiltersOut']

/**
 * 快取鍵**不在 `inventoryKey` 底下**：標記已看會改那個前綴底下的每一份（`withWatch`），而這一份不是牆。
 * 選項不隨換頁、排序改變，所以與牆分開問。
 */
export function inventoryFiltersQueryOptions(libraryId: string) {
  return queryOptions({
    queryKey: ['inventoryFilters', libraryId],
    queryFn: () => apiGet<InventoryFilters>(`/inventory/${encodeURIComponent(libraryId)}/filters`),
    retry: retryUnlessRefused,
  })
}

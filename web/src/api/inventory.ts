import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'
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

/** 媒體庫端點的拒絕（`api/inventory.py` 的 `_refusal`）：`reason` 挑句子，`detail` 是原文。 */
export interface InventoryRefusal {
  reason: 'account_disabled' | 'library_not_visible' | 'jellyfin_unreachable'
  detail: string
}

const REASONS: readonly InventoryRefusal['reason'][] = [
  'account_disabled',
  'library_not_visible',
  'jellyfin_unreachable',
]

/**
 * 錯誤是不是媒體庫端點說得出理由的那幾種（與 `refusalOf`、`routeRefusalOf` 同一個形狀）。
 * 後端不可達、或理由不在這份封閉集合裡時是 `null`。
 */
export function inventoryRefusal(error: unknown): InventoryRefusal | null {
  if (!(error instanceof ApiError)) return null
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null) return null
  const reason = (detail as { reason?: unknown }).reason
  if (typeof reason !== 'string' || !REASONS.includes(reason as InventoryRefusal['reason'])) {
    return null
  }
  const text = (detail as { detail?: unknown }).detail
  return {
    reason: reason as InventoryRefusal['reason'],
    detail: typeof text === 'string' ? text : '',
  }
}

/**
 * 說得出理由的拒絕是答案不是故障，不重試：TanStack Query 預設重試三次、間隔加倍，「找不到這個媒體庫」
 * 會晚七秒才出現，被停用的帳號也要等同樣久才被送回登入頁（票 03 實跑量到）。其餘錯誤照預設。
 */
export function retryUnlessRefused(failures: number, error: Error): boolean {
  return inventoryRefusal(error) === null && failures < 3
}

export const inventoriesQueryOptions = queryOptions({
  queryKey: ['inventory'],
  queryFn: () => apiGet<InventoryLibrary[]>('/inventory'),
  retry: retryUnlessRefused,
})

/** 第 1 頁不帶 `?page=`：網址與快取鍵都少一種寫法。 */
export function inventoryQueryOptions(libraryId: string, page: number) {
  return queryOptions({
    queryKey: ['inventory', libraryId, page],
    queryFn: () =>
      apiGet<Inventory>(
        `/inventory/${encodeURIComponent(libraryId)}${page > 1 ? `?page=${page}` : ''}`,
      ),
    retry: retryUnlessRefused,
  })
}

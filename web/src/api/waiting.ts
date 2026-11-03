import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** 每一份清單等著幾件（`berth/api/waiting.py`）。三格加起來是 Discord「有 N 件等你處理」的 N。 */
export type WaitingCounts = Schemas['WaitingCountsOut']

/**
 * 頁首與區塊分頁的件數（M5.5 票 07）。只有管理員問得到（後端 403）。
 *
 * 每分鐘重讀一次：新的一件多半來自背景（管線、巡檢、RSS），這一頁收不到推播。按完按鈕由
 * `router.ts` 的 `recountAfterActions` 失效，不必讓每一個動作都知道頁首。
 */
export const waitingQueryOptions = queryOptions({
  queryKey: ['waiting'],
  queryFn: ({ signal }) => apiGet<WaitingCounts>('/waiting', { signal }),
  refetchInterval: 60_000,
  staleTime: 30_000,
})

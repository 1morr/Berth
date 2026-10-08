import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { healthQueryOptions } from '../api/health'
import { recheckRoutes, routesQueryOptions } from '../api/routes'

/** 跑著的那一輪多久重讀一次進度：與精靈頁 3 同一個節奏（M4 票 43）。 */
export const PROGRESS_INTERVAL_MS = 1500

/**
 * 一條或全部 Route 改動之後，畫著它的每一處都要重問：Route 設定頁、健康頁（泊位板與 Route 區塊）、
 * 媒體庫的切換列（名稱與啟用都顯示在那裡）。檢查結果不論成敗都已經寫進去了，所以失敗時也要重問。
 */
export function refreshRoutes(queryClient: QueryClient) {
  // `void`：畫面不必等重抓完才解除按鈕，回傳的 promise 是刻意不等的。
  void queryClient.invalidateQueries({ queryKey: routesQueryOptions.queryKey })
  void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey })
  void queryClient.invalidateQueries({ queryKey: ['inventory'] })
}

/**
 * 「全部重新檢查」（M4 票 59）：Route 設定頁、健康頁與換了一台 qBittorrent 之後的設定頁共用。
 * 跑著的時候由呼叫端輪詢它自己讀的那一份（`refetchInterval: PROGRESS_INTERVAL_MS`）。
 */
export function useRecheckRoutes() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: recheckRoutes,
    // 開跑就重讀一次：換台作廢的檢查（`forget_route_checks`）要立刻畫出來，不等第一次輪詢——否則頭 1.5 秒
    // 畫的還是換台之前快取的「已繫上 6 / 6」。
    onMutate: () => refreshRoutes(queryClient),
    onSettled: () => refreshRoutes(queryClient),
  })
}

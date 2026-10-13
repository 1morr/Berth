import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { healthDetailQueryOptions, healthQueryOptions, type HealthDetail } from '../api/health'
import type { ServiceKind } from '../api/schemas'
import { testService } from '../api/settings'

export type ServiceCheck = UseMutationResult<HealthDetail, Error, ServiceKind>

/**
 * 重測一個服務（`POST /settings/services/{kind}/test`）。頁面自己持有它：健康卡的「重新檢查」
 * 與連線表單存完之後的重測是同一支，卡片上的結果才是剛剛那一次。
 */
export function useServiceCheck(): ServiceCheck {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (kind: ServiceKind) => testService(kind),
    // 設定頁與健康頁讀同一份快取，換掉它兩頁都是新的。
    onSuccess: (fresh) => {
      queryClient.setQueryData(healthDetailQueryOptions.queryKey, fresh)
      // `void`：匿名的那一支重抓完之前按鈕不必一直轉，回傳的 promise 是刻意不等的。
      void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey, exact: true })
    },
  })
}

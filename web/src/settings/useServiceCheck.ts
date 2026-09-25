import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { healthDetailQueryOptions, healthQueryOptions, type HealthDetail } from '../api/health'
import type { ServiceKind } from '../api/schemas'
import { servicesQueryOptions, testService } from '../api/settings'

export type ServiceCheck = UseMutationResult<HealthDetail, Error, ServiceKind>

/**
 * 重測一個服務（`POST /settings/services/{kind}/test`）。頁面自己持有它：健康卡的「重新檢查」
 * 與連線表單存完之後的重測是同一支，卡片上的結果才是剛剛那一次。
 */
export function useServiceCheck(): ServiceCheck {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (kind: ServiceKind) => testService(kind),
    // 健康頁看的是同一份資料，所以兩份快取一起換掉。
    onSuccess: (fresh) => {
      queryClient.setQueryData(servicesQueryOptions.queryKey, fresh)
      queryClient.setQueryData(healthDetailQueryOptions.queryKey, fresh)
      // `void`：匿名的那一支重抓完之前按鈕不必一直轉，回傳的 promise 是刻意不等的。
      void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey, exact: true })
    },
  })
}

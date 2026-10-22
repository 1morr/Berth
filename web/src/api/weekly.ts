import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiGet, signedOut } from './client'
import type { Schemas } from './schemas'

/** 歷史清單的一列（`berth/api/weekly.py` 的 `WeeklyLineOut`），最新一週在前。 */
export type WeeklyLine = Schemas['WeeklyLineOut']

/** 一週的一整份（`WeeklyReportOut`）：入庫、修了什麼、產生當下還在等人的。 */
export type WeeklyReport = Schemas['WeeklyReportOut']

/** 入庫的一部作品。`media` 是 `null` 就是作品後來被刪了。 */
export type ImportedWork = Schemas['ImportedWorkOut']

export function weeklyQueryOptions() {
  return queryOptions({
    queryKey: ['weekly'],
    queryFn: () => apiGet<WeeklyLine[]>('/weekly'),
  })
}

/**
 * 某一週。404（沒有這一份）是答案不是故障，不重試：預設的三次退避會讓「沒有這一週的週報」晚七秒才出現。
 * 週報產生之後不再改，所以也不必重抓。
 */
export function weeklyReportQueryOptions(id: number) {
  return queryOptions({
    queryKey: ['weekly', id],
    queryFn: () => apiGet<WeeklyReport>(`/weekly/${id}`),
    retry: (failures, error) =>
      !signedOut(error) && !(error instanceof ApiError && error.status === 404) && failures < 3,
    staleTime: Infinity,
  })
}

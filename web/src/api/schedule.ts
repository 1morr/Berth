import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** 這一週（`berth/api/schedule.py`）。**失敗也是 200**，同探索頁。 */
export type Schedule = Schemas['ScheduleOut']

/** 一部作品這一週的一集。 */
export type ScheduleCard = Schemas['ScheduleCardOut']

/**
 * 時間表（M5.5 票 09）。後端記六小時，重讀只讀資料庫；狀態每次照資料庫算，所以**不設 `staleTime`**：
 * 在作品頁訂閱完回到這一頁，重新掛上時就再讀一次，那張卡當場變「已訂閱」。
 */
export const scheduleQueryOptions = queryOptions({
  queryKey: ['schedule'],
  queryFn: ({ signal }) => apiGet<Schedule>('/schedule', { signal }),
})

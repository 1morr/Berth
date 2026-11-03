import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** 追更頁（`berth/api/keeping_up.py`，M5.5 票 12）。只有管理員問得到（後端 403）。 */
export type KeepingUp = Schemas['KeepingUpOut']

/** 一部訂閱的作品。 */
export type TrackedWork = Schemas['TrackedWorkOut']

/** 晚的一集。 */
export type LateEpisode = Schemas['LateEpisodeOut']

/** 三段：要你動手、準時、斷更很久（宣告順序同後端的 `KeepingUpSection`）。 */
export type KeepingUpSection = Schemas['KeepingUpSection']

/**
 * 只讀資料庫，每次照資料庫算；不設 `staleTime`：從作品頁或 Job 頁處理完回來，重新掛上時就再讀一次。
 * 鍵不放在 `['schedule']` 底下：時間表的「重試」失效那一支，不必連這一份一起重讀。
 */
export const keepingUpQueryOptions = queryOptions({
  queryKey: ['keeping-up'],
  queryFn: ({ signal }) => apiGet<KeepingUp>('/schedule/tracking', { signal }),
})

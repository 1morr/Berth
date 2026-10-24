import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** AI 活動頁（M5 票 14，`.scratch/m5/ai-activity-shape.md`）：助理替人做過的每一件寫入，新的在前。 */
export type AiActivity = Schemas['ActivityOut']

export type AiActivityEntry = Schemas['ActivityEntryOut']

export const AI_ACTIVITY_KEY = ['ai-activity'] as const

export const aiActivityQueryOptions = queryOptions({
  queryKey: AI_ACTIVITY_KEY,
  queryFn: ({ signal }) => apiGet<AiActivity>('/ai-activity', { signal }),
})

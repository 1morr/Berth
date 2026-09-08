import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'

export type HealthStatus = 'ok' | 'degraded'

export interface Health {
  status: HealthStatus
  version: string
  /** 精靈跑完了沒。這一支是匿名的，所以還沒有人登入時也答得出來（票 07）。 */
  setup_completed: boolean
}

export const healthQueryOptions = queryOptions({
  queryKey: ['health'],
  queryFn: () => apiGet<Health>('/health'),
})

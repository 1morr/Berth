import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'

export type HealthStatus = 'ok' | 'degraded'

export interface Health {
  status: HealthStatus
  version: string
}

export const healthQueryOptions = queryOptions({
  queryKey: ['health'],
  queryFn: () => apiGet<Health>('/health'),
})

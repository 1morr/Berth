import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'

/** 與 `berth/domain/enums.py` 的 `Role` 對齊。由 Jellyfin 的 `Policy.IsAdministrator` 決定。 */
export type Role = 'admin' | 'user'

export interface Me {
  name: string
  role: Role
}

export interface Credentials {
  username: string
  password: string
}

/**
 * session cookie 是 httpOnly 的，JavaScript 讀不到它——「有沒有登入」只能問後端。
 * 未登入時這一支回 401，路由守衛據此導向 `/login`（票 07）。
 */
export const meQueryOptions = queryOptions({
  queryKey: ['auth', 'me'],
  queryFn: () => apiGet<Me>('/auth/me'),
  // 登入狀態是門禁的一部分，不要拿快取賭它還成立。
  retry: false,
  staleTime: 0,
})

export function signIn(body: Credentials): Promise<Me> {
  return apiPost<Me>('/auth/login', body)
}

/** 回 204：session 早就失效的人也照樣成功，cookie 一樣會被清掉。 */
export function signOut(): Promise<void> {
  return apiPost<void>('/auth/logout')
}

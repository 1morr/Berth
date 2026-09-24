import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { Schemas } from './schemas'

/** 由 Jellyfin 的 `Policy.IsAdministrator` 決定。 */
export type Role = Schemas['Role']

export type Me = Schemas['MeOut']

export type Credentials = Schemas['LoginIn']

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

/**
 * 登入那一個 mutation 的鍵。它的 401 是帳密不對，不是 session 結束——「401 就導回登入頁」
 * （`router.ts`）靠它認出這一支。
 */
export const SIGN_IN_KEY = ['auth', 'login'] as const

export function signIn(body: Credentials): Promise<Me> {
  return apiPost<Me>('/auth/login', body)
}

/** 回 204：session 早就失效的人也照樣成功，cookie 一樣會被清掉。 */
export function signOut(): Promise<void> {
  return apiPost<void>('/auth/logout')
}

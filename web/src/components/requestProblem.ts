import { ApiError } from '../api/client'

/** 對 Berth 自己的一次請求為什麼沒成（M4 票 21）。後端說得出理由的拒絕由各頁自己說，這裡是其餘的。 */
export type RequestProblem = 'offline' | 'invalid' | 'conflict' | 'server'

export const PROBLEM_TEXT = {
  offline: 'request.offline',
  invalid: 'request.invalid',
  conflict: 'request.conflict',
  server: 'request.server',
} as const satisfies Record<RequestProblem, string>

/**
 * 分類：送不到（沒有 HTTP 回應）是 Berth 沒在跑或斷線；422 是這一次送的東西它不收（多半是畫面過時了）；
 * 409 是與它現在的狀態衝突；其餘是它自己出錯。原本這幾種一律說「Berth 後端可能沒在跑」——422 也是。
 */
export function requestProblem(error: unknown): RequestProblem {
  if (!(error instanceof ApiError)) return 'offline'
  if (error.status === 422) return 'invalid'
  if (error.status === 409) return 'conflict'
  return 'server'
}

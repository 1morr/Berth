import { ApiError } from '../api/client'

/** 對 Berth 自己的一次請求為什麼沒成（M4 票 21）。後端說得出理由的拒絕由各頁自己說，這裡是其餘的。 */
export type RequestProblem =
  | 'offline'
  | 'invalid'
  | 'conflict'
  | 'server'
  | 'signedOut'
  | 'ownerElsewhere'
  | 'notAdministrator'

export const PROBLEM_TEXT = {
  offline: 'request.offline',
  invalid: 'request.invalid',
  conflict: 'request.conflict',
  server: 'request.server',
  signedOut: 'request.signedOut',
  ownerElsewhere: 'request.ownerElsewhere',
  notAdministrator: 'request.notAdministrator',
} as const satisfies Record<RequestProblem, string>

/** 這兩種的下一步是登入：畫面給一個登入連結。 */
export const SIGN_IN_PROBLEMS: ReadonlySet<RequestProblem> = new Set([
  'signedOut',
  'ownerElsewhere',
])

/**
 * 分類：送不到（沒有 HTTP 回應）是 Berth 沒在跑或斷線；422 是這一次送的東西它不收（多半是畫面過時了）；
 * 409 是與它現在的狀態衝突；其餘是它自己出錯。原本這幾種一律說「Berth 後端可能沒在跑」——422 也是。
 *
 * **門禁的 401 / 403**（M4 票 25）看這一頁讀到的精靈狀態——`ownerPending` 是這一頁還以為沒有擁有者
 * （匿名的頁 1）。那時被要求登入，只可能是擁有者剛在另一個瀏覽器成立了；其餘的 401 是 session 失效，門禁
 * 分不出這兩種（兩者都是沒帶 session）。403 有兩種（`api/gate.py`；我們的 client 一律帶 CSRF 標頭，那一種
 * 不會出現）：擁有者成立之後是不是管理員；之前是「先做完頁 1」——畫面走在後端前面，與現狀衝突。
 */
export function requestProblem(
  error: unknown,
  { ownerPending = false }: { ownerPending?: boolean } = {},
): RequestProblem {
  if (!(error instanceof ApiError)) return 'offline'
  if (error.status === 401) return ownerPending ? 'ownerElsewhere' : 'signedOut'
  if (error.status === 403) return ownerPending ? 'conflict' : 'notAdministrator'
  if (error.status === 422) return 'invalid'
  if (error.status === 409) return 'conflict'
  return 'server'
}

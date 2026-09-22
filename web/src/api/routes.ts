import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiDelete, apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { RouteView, Schemas } from './schemas'

/**
 * 後端 `RouteRejectedError` 的理由（`berth/domain/enums.py` 的 `RouteRefusal`）。封閉集合而不是
 * `string`：每一種都有自己的一句話與下一步（PRODUCT 原則 4）。形狀與送單的 `JobRefusal` 相同。
 */
export type RouteRefusal = Schemas['RouteRefusal']

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤（M2 票 02）。 */
const REASONS: ReasonSet<RouteRefusal> = {
  library_missing: true,
  library_unsupported: true,
  target_not_in_library: true,
  target_taken: true,
  jellyfin_unreachable: true,
  route_missing: true,
  route_in_use: true,
  route_unhealthy: true,
  route_conflict: true,
}

/** 有多少東西指著一條 Route。與清單那一列（`ManagedRoute`）同一組詞。 */
export type RouteUsage = Pick<ManagedRoute, 'jobs' | 'ledger_entries'>

/** 拒絕的完整形狀：封閉集合的理由，加上服務回的原文。 */
export interface RouteRefusalDetail {
  reason: RouteRefusal
  detail: string
  /** `route_in_use` 帶的兩個數字（票 14a），畫面照它說「N 筆下載、M 個入庫檔案」。 */
  usage?: RouteUsage
}

/**
 * 這一次失敗是「後端說不行」還是別的。認不得的理由回 `null`，畫面落回一句通用的話。
 *
 * 理由與原文的解析與另外兩組共用（`api/refusal.ts`）；這裡多讀的是 `route_in_use` 才有的
 * 那兩個數字，它們在後端是 `RouteRefusalOut` 上兩格可有可無的欄位。
 */
export function routeRefusalOf(error: unknown): RouteRefusalDetail | null {
  const refusal = parseRefusal(error, REASONS)
  // 第二個條件在 `parseRefusal` 回了東西之後永遠成立，但寫出來才拿得到 TypeScript 的縮窄
  // ——不然這裡只能對 `error` 裸 cast 一次。
  if (refusal === null || !(error instanceof ApiError)) return refusal
  // `detail` 在 `ApiError` 上是 `unknown`（它裝得下驗證錯誤那種陣列），而理由已經確認是
  // Route 的那一組，所以這一份 body 就是 `RouteRefusalOut`；兩格是選填，所以是 `Partial`。
  const { jobs, ledger_entries: ledgerEntries } = error.detail as Partial<
    Schemas['RouteRefusalOut']
  >
  return {
    ...refusal,
    ...(typeof jobs === 'number' && typeof ledgerEntries === 'number'
      ? { usage: { jobs, ledger_entries: ledgerEntries } }
      : {}),
  }
}

/**
 * Route 設定頁（`/settings/routes`，票 14、`.scratch/m1/route-settings-shape.md`）。
 *
 * 誰進得來由後端門禁決定：永遠只有 admin（票 14a）。精靈第 7 步的「刪除」不打這裡，
 * 它走 `deleteSetupRoute`（`api/setup.ts`），跟著精靈的門禁。
 */

/** 一條 Route，加上有多少下載與入庫檔案指著它（刪不得時說得出為什麼）。 */
export type ManagedRoute = Schemas['ManagedRouteOut']

/** Jellyfin 現查回來的一個媒體庫，與它哪幾條路徑已經是別條 Route 的。 */
export type LibraryOption = Schemas['LibraryOptionOut']

export type RouteInput = Schemas['RouteIn']

/** 建立之後只改得了這三個（使用者拍板）：slug 與寫入目標是 Route 的身分。 */
export type RouteEdit = Schemas['RouteEditIn']

export const routesQueryOptions = queryOptions({
  queryKey: ['routes'],
  queryFn: () => apiGet<ManagedRoute[]>('/routes'),
})

/**
 * 媒體庫與路徑，**向 Jellyfin 現查**。按下「新增 Route」才打（shape brief §3）：這一頁多數時候
 * 是在看狀態，不該每開一次就去問 Jellyfin。
 */
export const libraryOptionsQueryOptions = queryOptions({
  queryKey: ['jellyfin', 'libraries'],
  queryFn: () => apiGet<LibraryOption[]>('/jellyfin/libraries'),
})

/** 新增並立刻跑五條纜繩。檢查紅燈不是錯誤：Route 照樣建立、維持停用。 */
export function createRoute(input: RouteInput): Promise<RouteView> {
  return apiPost<RouteView>('/routes', input)
}

/** 修改並重跑檢查。從停用到啟用而檢查是紅的：409 `route_unhealthy`。 */
export function updateRoute(id: number, edit: RouteEdit): Promise<RouteView> {
  return apiPut<RouteView>(`/routes/${id}`, edit)
}

/** 明確的刪除。被下載或帳本指著：409 `route_in_use`。 */
export function deleteRoute(id: number): Promise<void> {
  return apiDelete(`/routes/${id}`)
}

/** 重新檢查這一條。只是診斷，不動啟用。 */
export function recheckRoute(id: number): Promise<RouteView> {
  return apiPost<RouteView>(`/routes/${id}/check`)
}

import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { accessRefusal, retryUnlessRefused } from './jellyfin'
import { refusalOf, type JobRefusal } from './jobs'
import type { ReasonSet } from './refusal'
import { routeRefusalOf } from './routes'

/**
 * 三組拒絕共用的解析（`api/refusal.ts`，M2 票 02）。
 *
 * 理由的封閉集合由 `pnpm gen:api` 從後端的 OpenAPI 產出（`schema.d.ts`），所以「少一種理由」
 * 是編譯錯誤而不是執行期的空白；這裡驗的是**執行期那一半**：認不得的理由要落回 `null`，
 * 認得的要把原文一起帶出來。
 */

function refused(status: number, detail: unknown): ApiError {
  return new ApiError(status, 'refused', detail)
}

describe('拒絕的解析', () => {
  it('認得的理由連同原文一起帶出來', () => {
    const refusal = refusalOf(refused(409, { reason: 'route_disabled', detail: 'films' }))

    expect(refusal).toEqual({ reason: 'route_disabled', detail: 'films' })
  })

  it('認不得的理由是 `null`——畫面落回一句通用的話，不是一條 i18n key', () => {
    // 後端跑在前面（升級了後端，分頁還沒重新整理）時走到這裡。
    expect(refusalOf(refused(409, { reason: 'reason_from_the_future', detail: '' }))).toBeNull()
  })

  it('不是後端回的錯誤就不是拒絕', () => {
    expect(refusalOf(new TypeError('Failed to fetch'))).toBeNull()
    expect(refusalOf(refused(500, 'internal server error'))).toBeNull()
  })

  it('`detail` 不是字串時是空字串，不是 `undefined`', () => {
    // 畫面直接把它印出來，所以這一格永遠要是字串。
    expect(refusalOf(refused(422, { reason: 'media_missing' }))?.detail).toBe('')
  })

  it('繼承來的屬性不算——`{reason: "constructor"}` 不是一種理由', () => {
    expect(refusalOf(refused(422, { reason: 'constructor', detail: '' }))).toBeNull()
  })
})

describe('Route 的拒絕', () => {
  it('`route_in_use` 另外帶引用數，畫面照它說 N 筆下載、M 個入庫檔案', () => {
    const error = refused(409, {
      reason: 'route_in_use',
      detail: 'jobs=2 · ledger_entries=3',
      jobs: 2,
      ledger_entries: 3,
    })

    expect(routeRefusalOf(error)?.usage).toEqual({ jobs: 2, ledger_entries: 3 })
  })

  it('其餘理由沒有引用數', () => {
    expect(routeRefusalOf(refused(404, { reason: 'route_missing', detail: '7' }))?.usage).toBe(
      undefined,
    )
  })
})

describe('Jellyfin 權限閘門的拒絕', () => {
  it('`sort_not_offered` 是說得出理由的拒絕', () => {
    // 手抄的那一份漏了它（M2 票 02）：於是排序鍵不在這種媒體庫的選單上時，前端把後端
    // 已經說清楚的 422 當成「沒說理由」。
    const refusal = accessRefusal(
      refused(422, { reason: 'sort_not_offered', detail: 'DatePlayed' }),
    )

    expect(refusal).toEqual({ reason: 'sort_not_offered', detail: 'DatePlayed' })
  })

  it('說得出理由的拒絕不重試——答案不是故障', () => {
    // 重試三次、間隔加倍的話，「找不到這個媒體庫」會晚七秒才出現在畫面上（票 03 實跑量到）。
    const refusal = refused(404, { reason: 'library_not_visible', detail: '' })

    expect(retryUnlessRefused(0, refusal)).toBe(false)
    expect(retryUnlessRefused(0, refused(422, { reason: 'sort_not_offered', detail: '' }))).toBe(
      false,
    )
  })

  it('其餘錯誤照 TanStack Query 的預設重試三次', () => {
    const broken = new TypeError('Failed to fetch')

    expect(retryUnlessRefused(0, broken)).toBe(true)
    expect(retryUnlessRefused(3, broken)).toBe(false)
  })
})

/**
 * 執行期的成員表是**總表**：型別編譯後就沒了，所以 `parseRefusal` 仍需要一份列出來的集合，
 * 但它少一種或多一種都是編譯錯誤。
 *
 * 這一段跑不到任何執行期的東西——它是編碼下來的閘門本身。`@ts-expect-error` 在**那一行沒有
 * 錯誤時**會讓 `tsc` 紅，所以有人把 `ReasonSet` 放寬成 `Partial<Record<…>>` 時，紅的就是這裡；
 * 手動驗過而沒寫下來的閘門會隨 session 一起消失。
 */
describe('封閉集合的閘門', () => {
  it('少一種理由是編譯錯誤', () => {
    // @ts-expect-error 缺了 `media_missing` 以外的八種。
    const incomplete: ReasonSet<JobRefusal> = { media_missing: true }

    expect(incomplete).toBeTruthy()
  })

  it('多一種後端沒有的理由也是編譯錯誤', () => {
    const extra: ReasonSet<JobRefusal> = {
      media_missing: true,
      route_missing: true,
      route_kind_mismatch: true,
      route_disabled: true,
      route_unhealthy: true,
      source_unavailable: true,
      job_missing: true,
      not_retryable: true,
      not_replannable: true,
      // @ts-expect-error 後端的 `JobRefusal` 裡沒有這一種。
      reason_from_the_future: true,
    }

    expect(extra).toBeTruthy()
  })
})

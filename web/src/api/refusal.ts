import { ApiError } from './client'

/**
 * 後端說不行的那一份：`{reason, detail}`（plan §6）。三組拒絕——送單（`api/jobs.ts`）、
 * Route 設定（`api/routes.ts`）、Jellyfin 權限閘門（`api/jellyfin.ts`）——是同一個形狀，
 * 所以解析只有這一份。
 *
 * **理由的封閉集合一律從 `schema.d.ts` 來**（M2 票 02）：三組原本各在自己的檔案裡手抄一份
 * 字面聯集，後端加一種理由時沒有任何東西會紅，畫面上只會少一句話。現在後端的 enum 進了
 * OpenAPI，少寫一種是 `tsc` 的事。
 */

/** 每一種理由都要有一格。少一種、多一種都是編譯錯誤——這就是那道閘門。 */
export type ReasonSet<R extends string> = Readonly<Record<R, true>>

export interface Refusal<R extends string> {
  reason: R
  detail: string
}

/**
 * 這一次失敗是「後端說不行」還是「網路壞了」。
 *
 * **認不得的理由回 `null`**，畫面落回一句誠實的通用訊息：後端跑在前面（升級了後端還沒重新整理
 * 分頁）時，使用者該看到的是一句話，不是一條沒翻譯到的 i18n key。
 */
export function parseRefusal<R extends string>(
  error: unknown,
  reasons: ReasonSet<R>,
): Refusal<R> | null {
  if (!(error instanceof ApiError)) return null
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null) return null
  const reason = (detail as { reason?: unknown }).reason
  if (typeof reason !== 'string' || !Object.hasOwn(reasons, reason)) return null
  const text = (detail as { detail?: unknown }).detail
  return { reason: reason as R, detail: typeof text === 'string' ? text : '' }
}

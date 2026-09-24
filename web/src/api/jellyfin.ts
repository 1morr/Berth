import { apiDelete, apiPost, signedOut } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/**
 * 替 session 那個人向 Jellyfin 讀寫的那幾件事共用的形狀（`berth/api/jellyfin.py`、`services/jellyfin_access.py`）：
 * 深連結的主機、觀看狀態、權限閘門的拒絕、標記已看。媒體庫、首頁兩列與 Media 詳情的觀看區都用它們
 * （M1.5 票 03–08）。前端不送、也拿不到任何 Jellyfin 使用者 id。
 */

/** 深連結開在哪一台主機上。媒體庫與設定頁共用。 */
export type JellyfinWeb = Schemas['JellyfinWebOut']

/** 這位使用者在 Jellyfin 看到哪了（`services/watch.py`、M1.5 票 05）。判定在後端。 */
export type WatchState = Schemas['WatchStateOut']

/**
 * 權限閘門的拒絕（`api/jellyfin.py` 的 `access_refusal`，媒體庫與標記已看共用）：`reason` 挑句子，
 * `detail` 是原文。理由的封閉集合從 OpenAPI 來（`berth/domain/enums.py` 的 `AccessRefusal`）。
 */
export type AccessRefusal = Schemas['AccessRefusalOut']

/**
 * 執行期認得的那幾種。`ReasonSet` 是總表，少一種或多一種都是編譯錯誤——手抄的那一份漏了
 * `sort_not_offered`，於是排序鍵不在選單上時前端把它當成「沒說理由」，退回通用訊息並重試
 * 三次（M2 票 02）。
 */
const REASONS: ReasonSet<AccessRefusal['reason']> = {
  account_disabled: true,
  library_not_visible: true,
  item_not_visible: true,
  jellyfin_unreachable: true,
  sort_not_offered: true,
}

/**
 * 錯誤是不是媒體庫端點說得出理由的那幾種（與 `refusalOf`、`routeRefusalOf` 同一個形狀）。
 * 後端不可達、或理由不在這份封閉集合裡時是 `null`。
 */
export function accessRefusal(error: unknown): AccessRefusal | null {
  return parseRefusal(error, REASONS)
}

/**
 * 說得出理由的拒絕是答案不是故障，不重試：TanStack Query 預設重試三次、間隔加倍，「找不到這個媒體庫」
 * 會晚七秒才出現，被停用的帳號也要等同樣久才被送回登入頁（票 03 實跑量到）。其餘錯誤照預設。
 */
export function retryUnlessRefused(failures: number, error: Error): boolean {
  return accessRefusal(error) === null && !signedOut(error) && failures < 3
}

/**
 * 標為已看（`POST`）或未看（`DELETE`），回寫入之後的狀態。寫的是 session 那個人的紀錄，前端不送任何
 * 使用者 id。**標為未看復原不了**（觀看次數與時間被清掉，劇集清的是每一集），先確認是畫面的事。
 */
export function markPlayed(itemId: string, played: boolean): Promise<WatchState> {
  const path = `/jellyfin/items/${encodeURIComponent(itemId)}/played`
  return played ? apiPost<WatchState>(path) : apiDelete<WatchState>(path)
}

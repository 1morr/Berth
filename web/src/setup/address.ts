import type { TFunction } from 'i18next'

/**
 * 使用者填的位址沒寫 `http://` 或 `https://`（M4 票 25）。
 *
 * 後端連都不連就失敗（httpx 把 `nas:8080` 讀成協定 `nas`），原本被說成「連不上，確認 port」。照 *arr
 * 的做法**不自動補**——補 http 還是 https 是猜，猜錯就變成另一種錯——送出前在欄位下直接說。空的不算：
 * 那是「必填」那一句的事。
 */
export function lacksScheme(address: string): boolean {
  const trimmed = address.trim()
  return trimmed !== '' && !/^https?:\/\//i.test(trimmed)
}

/** 位址欄送出前的那一句：沒填、或沒寫協定。服務頁與索引站的既有表單共用；有這一句就不送。 */
export function addressError(t: TFunction, address: string): string | undefined {
  if (!address.trim()) return t('connect.error.blank')
  if (lacksScheme(address)) return t('connect.error.scheme')
  return undefined
}

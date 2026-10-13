import { useTranslation } from 'react-i18next'

import { relative, relativePast } from './relativeTime'

/**
 * 一個時間點：相對說法給人讀，絕對時間留在 `title` 與 `datetime` 裡。
 *
 * 維運頁面上「三分鐘前」與「三小時前」是完全不同的兩件事，但「2026-09-08T12:04:31Z」
 * 沒有人在掃視時算得出來——所以兩種都要有，而不是二選一。
 */
export function Timestamp({
  at,
  past = false,
}: {
  at: string | null
  /**
   * 伺服器記下的、已經發生的時間（檢查於、最後成功）。瀏覽器的時鐘比伺服器慢時它落在「未來」，原本說成
   * 「2 秒後」（M4 票 55 實測）：這種一律說成現在。預約的時間（下一批、重試於）不給。
   */
  past?: boolean
}) {
  const { t, i18n } = useTranslation()

  // 「沒有紀錄」而不是「尚未檢查」：這裡說的是**這個時間點**沒有值，與那一項的狀態無關
  // （紅著的服務也可能從來沒成功過）。
  if (!at) return <span className="value text-ink-dim">{t('health.never')}</span>

  const moment = new Date(at)
  return (
    <time dateTime={at} title={moment.toLocaleString(i18n.language)} className="value">
      {past ? relativePast(moment, i18n.language) : relative(moment, i18n.language)}
    </time>
  )
}

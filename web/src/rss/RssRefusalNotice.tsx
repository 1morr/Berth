import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { parseRssRefusal } from '../api/rss'
import { Notice } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'

/**
 * `/rss/*` 被拒時的那一塊：理由挑句子（`rss.refusal.*`），原文另外印在下面。讀不到上游
 * （`feed_unreachable`）各處說法不同，由呼叫端給那一句；`children` 是接在後面的動作（例如「再讀一次」）。
 */
export function RssRefusalNotice({
  error,
  unreachable,
  children,
}: {
  error: unknown
  unreachable: string
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const refusal = parseRssRefusal(error)

  // 後端沒說理由：照請求為什麼沒成說（M4 票 90）。
  if (refusal === null) return <RequestFailed error={error} lead={t('request.notDone')} />

  return (
    <Notice signal="blocked" label={t('common.failed')}>
      {refusal.reason === 'feed_unreachable' ? unreachable : t(`rss.refusal.${refusal.reason}`)}
      {refusal.detail ? (
        <span className="value block text-xs wrap-anywhere">{refusal.detail}</span>
      ) : null}
      {children}
    </Notice>
  )
}

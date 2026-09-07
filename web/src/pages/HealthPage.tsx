import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { healthQueryOptions } from '../api/health'

/**
 * M0 的佔位頁：證明前端、API 與資料庫在同一個程序裡串起來了。
 * 真正的頁面（探索、媒體庫、Job…）從票 05 開始，走 /impeccable。
 */
export function HealthPage() {
  const { t } = useTranslation()
  const health = useQuery(healthQueryOptions)

  return (
    <section className="rounded-lg border border-edge bg-surface p-6">
      <h2 className="text-lg font-medium">{t('health.title')}</h2>

      {health.isPending && <p className="mt-4 text-ink-muted">{t('health.checking')}</p>}

      {health.isError && (
        <p role="alert" className="mt-4 text-negative">
          {t('health.unreachable')}
        </p>
      )}

      {health.data && (
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
          <dt className="text-ink-muted">{t('health.backend')}</dt>
          <dd className={health.data.status === 'ok' ? 'text-positive' : 'text-negative'}>
            {t(`health.value.${health.data.status}`)}
          </dd>
          <dt className="text-ink-muted">{t('health.version')}</dt>
          <dd className="font-mono">{health.data.version}</dd>
        </dl>
      )}
    </section>
  )
}

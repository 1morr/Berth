import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { healthQueryOptions } from '../api/health'
import { Notice } from '../components/controls'

/**
 * M0 的佔位頁：證明前端、API 與資料庫在同一個程序裡串起來了。
 * 真正的健康頁在票 10（走 impeccable `shape`）。
 */
export function HealthPage() {
  const { t } = useTranslation()
  const health = useQuery(healthQueryOptions)

  return (
    <section className="border-2 border-rule bg-well">
      <h2 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
        {t('health.title')}
      </h2>

      <div className="px-4 py-4">
        {health.isPending && <p className="text-sm text-ink-dim">{t('health.checking')}</p>}

        {health.isError && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('health.unreachable')}
          </Notice>
        )}

        {health.data && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
            <dt className="label self-center text-ink-dim">{t('health.backend')}</dt>
            <dd className={health.data.status === 'ok' ? 'text-secured-ink' : 'text-blocked-ink'}>
              {t(`health.value.${health.data.status}`)}
            </dd>
            <dt className="label self-center text-ink-dim">{t('health.version')}</dt>
            <dd className="value">{health.data.version}</dd>
          </dl>
        )}
      </div>
    </section>
  )
}

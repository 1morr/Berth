import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { WeeklyReport } from '../api/weekly'
import { TEXT_LINK } from '../components/controls'
import { SectionHeading } from '../components/SectionHeading'
import { sumCounts } from './counts'
import { TypeCounts } from './TypeCounts'

/**
 * 還有什麼等人：產生那一刻的數字（快照），不是現在需要你——所以不塗任何信號色。
 * 巡檢開出的是 Issue 的一部分，另列一行、不另算進總數。
 */
export function WaitingSection({ waiting }: { waiting: WeeklyReport['waiting'] }) {
  const { t } = useTranslation()
  const issues = sumCounts(waiting.issues)
  const swept = sumCounts(waiting.swept)
  const total = waiting.review + issues + waiting.rss

  const reviewLabel = t('weekly.waiting.review')
  const issuesLabel = t('weekly.waiting.issues')
  const rssLabel = t('weekly.waiting.rss')
  const open = (what: string) => t('weekly.waiting.open', { what })

  return (
    <section aria-labelledby="weekly-waiting" className="grid gap-3">
      <SectionHeading
        id="weekly-waiting"
        label={t('weekly.waiting.title')}
        extra={
          total > 0 && (
            <p className="value text-xs text-ink-dim">
              {t('weekly.waiting.total', { count: total })}
            </p>
          )
        }
      />
      {total === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('weekly.waiting.empty')}</p>
      ) : (
        <dl className="grid gap-3">
          {waiting.review > 0 && (
            <Row label={reviewLabel} count={waiting.review}>
              <Link to="/review" aria-label={open(reviewLabel)} className={TEXT_LINK}>
                {t('weekly.waiting.openShort')}
              </Link>
            </Row>
          )}
          {issues > 0 && (
            <Row label={issuesLabel} count={issues} types={waiting.issues}>
              <Link to="/issues" aria-label={open(issuesLabel)} className={TEXT_LINK}>
                {t('weekly.waiting.openShort')}
              </Link>
            </Row>
          )}
          {swept > 0 && (
            <Row label={t('weekly.waiting.swept')} count={swept} types={waiting.swept}>
              <span className="text-xs text-ink-dim">{t('weekly.waiting.sweptNote')}</span>
            </Row>
          )}
          {waiting.rss > 0 && (
            <Row label={rssLabel} count={waiting.rss}>
              <Link to="/rss" aria-label={open(rssLabel)} className={TEXT_LINK}>
                {t('weekly.waiting.openShort')}
              </Link>
            </Row>
          )}
        </dl>
      )}
      <p className="max-w-prose text-sm text-ink-dim">{t('weekly.waiting.snapshot')}</p>
    </section>
  )
}

function Row({
  label,
  count,
  types,
  children,
}: {
  label: string
  count: number
  types?: Record<string, number>
  children: ReactNode
}) {
  return (
    <div className="grid gap-1 border-b border-rule pb-2 sm:grid-cols-[14rem_1fr] sm:gap-x-4">
      <dt className="text-sm text-ink">{label}</dt>
      <dd className="flex min-w-0 flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="grid min-w-0 gap-1">
          <span className="value text-sm text-ink">{count}</span>
          {types && <TypeCounts counts={types} />}
        </span>
        <span className="ms-auto">{children}</span>
      </dd>
    </div>
  )
}

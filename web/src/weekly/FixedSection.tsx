import { useTranslation } from 'react-i18next'

import type { WeeklyReport } from '../api/weekly'
import { SectionHeading } from '../components/SectionHeading'
import { sumCounts } from './counts'
import { TypeCounts } from './TypeCounts'

/** 修了什麼：每一種一列，0 的不列。 */
export function FixedSection({ fixed }: { fixed: WeeklyReport['fixed'] }) {
  const { t } = useTranslation()
  const resolved = sumCounts(fixed.resolved)
  const cleared = sumCounts(fixed.cleared)
  const total = fixed.approved + fixed.rematched + resolved + cleared

  const rows = [
    { key: 'approved', label: t('weekly.fixed.approved'), count: fixed.approved, types: null },
    { key: 'rematched', label: t('weekly.fixed.rematched'), count: fixed.rematched, types: null },
    { key: 'resolved', label: t('weekly.fixed.resolved'), count: resolved, types: fixed.resolved },
    { key: 'cleared', label: t('weekly.fixed.cleared'), count: cleared, types: fixed.cleared },
  ].filter((row) => row.count > 0)

  return (
    <section aria-labelledby="weekly-fixed" className="grid gap-3">
      <SectionHeading
        id="weekly-fixed"
        label={t('weekly.fixed.title')}
        extra={
          total > 0 && (
            <p className="value text-xs text-ink-dim">
              {t('weekly.fixed.total', { count: total })}
            </p>
          )
        }
      />
      {rows.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('weekly.fixed.empty')}</p>
      ) : (
        <dl className="grid gap-3">
          {rows.map((row) => (
            <div
              key={row.key}
              className="grid gap-1 border-b border-rule pb-2 sm:grid-cols-[14rem_1fr] sm:gap-x-4"
            >
              <dt className="text-sm text-ink">{row.label}</dt>
              <dd className="grid min-w-0 gap-1">
                <span className="value text-sm text-ink">{row.count}</span>
                {row.types && <TypeCounts counts={row.types} />}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}

import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { WeeklyLine } from '../api/weekly'
import { SectionHeading } from '../components/SectionHeading'
import { dayRange } from './dates'

const BOX = 'flex min-h-6 flex-wrap items-baseline gap-x-4 gap-y-1 border-2 px-3 py-2'

/** 歷來的週報：一週一列，最新在上，全部列出。目前這一週不是連結。 */
export function HistoryNav({
  lines,
  currentId,
}: {
  lines: WeeklyLine[]
  currentId: number | null
}) {
  const { t } = useTranslation()

  return (
    <nav aria-labelledby="weekly-history" className="grid gap-3">
      <SectionHeading id="weekly-history" label={t('weekly.history.title')} />
      <ul className="grid gap-2">
        {lines.map((line) => {
          const body = (
            <>
              <span className="value text-sm text-ink">
                {dayRange(line.first_day, line.last_day)}
              </span>
              <span className="value flex basis-full flex-wrap gap-x-3 text-xs text-ink-dim sm:basis-auto">
                <span>{t('weekly.history.works', { count: line.works })}</span>
                <span>{t('weekly.history.fixed', { count: line.fixed })}</span>
                <span>{t('weekly.history.waiting', { count: line.waiting })}</span>
              </span>
            </>
          )
          return (
            <li key={line.id} className="min-w-0">
              {line.id === currentId ? (
                <span aria-current="page" className={`${BOX} border-rule-strong bg-deck`}>
                  {body}
                </span>
              ) : (
                <Link
                  to="/weekly/$reportId"
                  params={{ reportId: String(line.id) }}
                  className={`${BOX} border-rule hover:border-rule-strong`}
                >
                  {body}
                </Link>
              )}
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

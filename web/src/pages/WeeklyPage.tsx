import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { weeklyQueryOptions, weeklyReportQueryOptions, type WeeklyReport } from '../api/weekly'
import { PAGE_TITLE, TEXT_LINK } from '../components/controls'
import { QueueLoading } from '../components/QueueLoading'
import { RequestFailed } from '../components/RequestFailed'
import { dayRange, monthDayTime } from '../weekly/dates'
import { FixedSection } from '../weekly/FixedSection'
import { HistoryNav } from '../weekly/HistoryNav'
import { ImportedSection } from '../weekly/ImportedSection'
import { WaitingSection } from '../weekly/WaitingSection'

/**
 * 週報 `/weekly`（最新一週）與 `/weekly/$reportId`（某一週）（M4 票 131，`.scratch/m4/weekly-report-shape.md`）。
 *
 * 模式是讀一份寫好的報告：這一週入庫了什麼、修了什麼、產生當下還欠什麼。**整頁沒有信號色**——
 * 「等你處理」是過去某一刻的快照，不是現在需要你。報告產生之後不再改，所以這一頁沒有任何動作。
 *
 * `reportId` 是網址上的原文：不是正整數的當作沒有這一週，不打後端。
 */
export function WeeklyPage({ reportId }: { reportId?: string }) {
  const { t } = useTranslation()
  const lines = useQuery(weeklyQueryOptions())

  const typed = reportId !== undefined
  const wanted = typed && /^[1-9]\d*$/.test(reportId) ? Number(reportId) : null
  // 沒指定就是最新一週（清單最新在前）。
  const shown = typed ? wanted : (lines.data?.[0]?.id ?? null)
  const report = useQuery({
    ...weeklyReportQueryOptions(shown ?? 0),
    enabled: shown !== null,
  })

  return (
    <div className="mx-auto grid w-full max-w-3xl gap-8 px-6 py-8">
      <Header report={report.data} />

      {lines.isPending ? (
        <QueueLoading />
      ) : !lines.data ? (
        <RequestFailed error={lines.error} lead={t('weekly.readFailed')} />
      ) : lines.data.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('weekly.none')}</p>
      ) : (
        <>
          {shown === null || (report.isError && isMissing(report.error)) ? (
            <p className="grid max-w-prose justify-items-start gap-2 text-sm text-ink">
              {t('weekly.notFound')}
              <Link to="/weekly" className={TEXT_LINK}>
                {t('weekly.toLatest')}
              </Link>
            </p>
          ) : report.isPending ? (
            <QueueLoading />
          ) : report.isError ? (
            <RequestFailed error={report.error} lead={t('weekly.readFailed')} />
          ) : (
            <>
              <ImportedSection works={report.data.imported} />
              <FixedSection fixed={report.data.fixed} />
              <WaitingSection waiting={report.data.waiting} />
            </>
          )}
          <HistoryNav lines={lines.data} currentId={shown} />
        </>
      )}
    </div>
  )
}

function isMissing(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

/** 抬頭：標題壓在重橫線上，旁邊是日期範圍；下一行是它什麼時候產生的。 */
function Header({ report }: { report: WeeklyReport | undefined }) {
  const { t } = useTranslation()
  return (
    <header className="grid gap-1">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h1 tabIndex={-1} className={PAGE_TITLE}>
          {t('weekly.title')}
        </h1>
        {report && (
          <p className="value basis-full text-sm text-ink sm:basis-auto">
            {dayRange(report.first_day, report.last_day)}
          </p>
        )}
      </div>
      {report && (
        <p className="text-sm text-ink-dim">
          <time dateTime={report.created_at}>
            {t('weekly.generated', { when: monthDayTime(new Date(report.created_at)) })}
          </time>
        </p>
      )}
    </header>
  )
}

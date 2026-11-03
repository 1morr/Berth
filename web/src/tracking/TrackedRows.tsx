import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { TrackedWork } from '../api/keepingUp'
import { INLINE_LINK } from '../components/controls'
import { Dot } from '../components/Dot'
import { episodeCode, seasonCode } from '../components/episodes'
import { SIGNAL_FILL } from '../components/signal'
import { displayRound } from '../i18n/displayRound'
import { monthDay } from '../schedule/week'
import { lateSpans, statusWords, stuckJob } from './status'

/**
 * 追更頁一段裡的作品（`.scratch/m5.5/tracking-shape.md`）。**同一份資料畫兩次**：`lg` 以上一張 `<table>`
 * （四欄對齊、掃得快），以下每部一塊、欄位上下疊（使用者 2026-11-04 定）。用 `hidden` 切而不是 CSS 把表格疊成
 * 塊：`display: block` 的表格在無障礙樹裡不再是表格，兩邊都要念得對。
 */
export function TrackedRows({
  works,
  caption,
}: {
  works: readonly TrackedWork[]
  caption: string
}) {
  const { t } = useTranslation()
  return (
    <>
      <table className="hidden w-full table-fixed border-collapse text-left lg:table">
        <caption className="sr-only">{caption}</caption>
        <colgroup>
          <col className="w-[26%]" />
          <col className="w-[16%]" />
          <col className="w-[14%]" />
          <col className="w-[12%]" />
          <col />
        </colgroup>
        <thead>
          <tr className="border-b-2 border-rule">
            {(['work', 'groups', 'aired', 'imported', 'status'] as const).map((column) => (
              <th key={column} scope="col" className="label px-3 py-2 font-normal text-ink-dim">
                {t(`tracking.column.${column}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {works.map((work) => (
            <tr key={work.media_id} className="border-b-2 border-rule align-baseline">
              <th scope="row" className="px-3 py-2.5 font-normal">
                <WorkLink work={work} />
              </th>
              <td className="px-3 py-2.5 text-sm text-ink">
                <Groups work={work} />
              </td>
              <td className="px-3 py-2.5">
                <Aired work={work} />
              </td>
              <td className="px-3 py-2.5">
                <Imported work={work} />
              </td>
              <td className="px-3 py-2.5">
                <Status work={work} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul aria-label={caption} className="grid gap-3 lg:hidden">
        {works.map((work) => (
          <li key={work.media_id} className="grid gap-2 border-2 border-rule bg-well px-4 py-3">
            <h3>
              <WorkLink work={work} />
            </h3>
            <Status work={work} />
            <dl className="grid grid-cols-[7rem_1fr] items-baseline gap-x-3 gap-y-1">
              <dt className="label text-ink-dim">{t('tracking.column.groups')}</dt>
              <dd className="text-sm text-ink">
                <Groups work={work} />
              </dd>
              <dt className="label text-ink-dim">{t('tracking.column.aired')}</dt>
              <dd>
                <Aired work={work} />
              </dd>
              <dt className="label text-ink-dim">{t('tracking.column.imported')}</dt>
              <dd>
                <Imported work={work} />
              </dd>
            </dl>
          </li>
        ))}
      </ul>
    </>
  )
}

function WorkLink({ work }: { work: TrackedWork }) {
  const { i18n } = useTranslation()
  return (
    <Link
      to="/media/$mediaId"
      params={{ mediaId: work.media_id }}
      className={`value text-sm text-ink wrap-anywhere ${INLINE_LINK}`}
    >
      {displayRound(i18n.language, { 'zh-Hant': work.title, en: work.title_en })}
    </Link>
  )
}

function Groups({ work }: { work: TrackedWork }) {
  const { t } = useTranslation()
  if (work.groups.length === 0) return <span className="text-ink-dim">{t('tracking.noGroup')}</span>
  return <span className="wrap-anywhere">{work.groups.join(t('weekly.typeJoin'))}</span>
}

function Aired({ work }: { work: TrackedWork }) {
  const { t, i18n } = useTranslation()
  if (work.conclusion === null)
    return <span className="text-sm text-ink-dim">{t('tracking.noSnapshot')}</span>
  if (!work.aired) return <span className="text-sm text-ink-dim">{t('tracking.notAired')}</span>
  return (
    <span className="value text-sm text-ink">
      {`${seasonCode(work.aired.season)}${episodeCode(work.aired.episode)}`}
      {work.aired.air_date && (
        <>
          {' '}
          <Dot />{' '}
          <time dateTime={work.aired.air_date} className="text-ink-dim">
            {monthDay(work.aired.air_date, i18n.language)}
          </time>
        </>
      )}
    </span>
  )
}

function Imported({ work }: { work: TrackedWork }) {
  const { t } = useTranslation()
  if (!work.imported)
    return <span className="text-sm text-ink-dim">{t('tracking.noneImported')}</span>
  return (
    <span className="value text-sm text-ink">
      {`${seasonCode(work.imported.season)}${episodeCode(work.imported.episode)}`}
    </span>
  )
}

/**
 * 「晚 N 天」是唯一塗漆的一格（`assigned`：現在需要你）；其餘是字（The Usual Stays Unpainted Rule）。
 * 晚的集、「可能是下一輪」、結論與「看這筆下載」用 `Dot` 隔開。
 */
function Status({ work }: { work: TrackedWork }) {
  const { t } = useTranslation()
  const words = statusWords(t, work)
  const job = stuckJob(work.late)
  const parts = [
    ...(work.late.length > 0 ? [lateSpans(work.late)] : []),
    ...(work.reason === 'next_run' ? [t('tracking.nextRun')] : []),
    ...words,
  ]
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink">
      {work.late_days !== null && (
        <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.assigned}`}>
          {t('tracking.late', { count: work.late_days })}
        </span>
      )}
      {parts.map((part, index) => (
        <span key={part} className="contents">
          {index > 0 && <Dot />}
          <span className={index === 0 && work.late.length > 0 ? 'value' : undefined}>{part}</span>
        </span>
      ))}
      {job && (
        <>
          <Dot />
          <Link to="/jobs/$hash" params={{ hash: job }} className={INLINE_LINK}>
            {t('tracking.seeJob')}
          </Link>
        </>
      )}
    </p>
  )
}

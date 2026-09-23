import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { reviewQueryOptions, type ReviewKind, type ReviewRow } from '../api/review'
import { PAGE_TITLE } from '../components/controls'
import { IssueRow } from '../issues/IssueRow'
import { AuditRow } from '../review/AuditRow'
import { DuplicateRow } from '../review/DuplicateRow'
import { PlanRow } from '../review/PlanRow'
import { UnmatchedRow } from '../review/UnmatchedRow'

/**
 * 審核佇列 `/review`（`.scratch/m2/review-shape.md`，M2 票 06）。
 *
 * **一列一件事的清單，不是牆**（brief §13）：篩出來常常只有一兩件，卡片牆說不出「有幾件事在等你」。
 * 成功的樣子是空清單。
 *
 * **三段，需要人動手的排前面**（使用者 2026-09-23 拍板）。後端已經照這個順序排好，這裡只是把
 * 連續的同一段切開、各給一條抬頭——**前端不重排**，排序只有後端一份。空的段不畫。
 */
export function ReviewPage() {
  const { t } = useTranslation()
  const queue = useQuery(reviewQueryOptions())
  // 按完那一列就消失了，焦點與畫面上都不剩任何東西說「成了」——這一句給看不見畫面的人。
  const [said, setSaid] = useState('')

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-6 px-6 py-8">
      <div className="grid gap-1 border-b-2 border-rule-strong pb-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className={PAGE_TITLE}>{t('review.title')}</h1>
          {queue.data && queue.data.total > 0 && (
            <p className="value text-xs text-ink-dim">
              {t('review.count', { count: queue.data.total })}
            </p>
          )}
        </div>
        {/* 超過上限時照實說（plan §6）：不分頁，那時候該修的是上游，不是默默少幾件。 */}
        {queue.data && queue.data.total > queue.data.rows.length && (
          <p className="text-xs text-ink-dim">
            {t('review.truncated', { shown: queue.data.rows.length, total: queue.data.total })}
          </p>
        )}
      </div>

      <p aria-live="polite" className="sr-only">
        {said}
      </p>

      {queue.isPending ? (
        <Loading />
      ) : !queue.data ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('review.off')}</p>
      ) : queue.data.rows.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('review.empty')}</p>
      ) : (
        sections(queue.data.rows).map((section) => (
          <section
            key={section.name}
            aria-labelledby={`review-${section.name}`}
            className="grid gap-3"
          >
            <h2
              id={`review-${section.name}`}
              className="flex flex-wrap items-baseline gap-x-2 border-b-2 border-rule-strong pb-1.5"
            >
              <span className="label text-ink">{t(`review.section.${section.name}`)}</span>
              <span className="value text-xs text-ink-dim">{section.rows.length}</span>
            </h2>
            <ul className="grid gap-3">
              {section.rows.map((row) => (
                <li key={`${row.kind}:${row.ref}`} className="min-w-0">
                  <Row row={row} onDone={setSaid} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}

/** 一列畫成哪個元件。**窮舉**：後端把新的 `kind` 加進聯集時，少一支是 `tsc` 的事。 */
function Row({ row, onDone }: { row: ReviewRow; onDone: (said: string) => void }) {
  switch (row.kind) {
    case 'plan':
      return <PlanRow row={row} onDone={onDone} />
    case 'audit':
      return <AuditRow row={row} onDone={onDone} />
    case 'unmatched':
      return <UnmatchedRow row={row} onDone={onDone} />
    case 'duplicate':
      return <DuplicateRow row={row} onDone={onDone} />
    case 'issue':
      return <IssueRow issue={row.issue} heading="h3" onDone={onDone} />
  }
}

type SectionName = 'decide' | 'look' | 'outside'

/**
 * 每一類落在哪一段（plan §6 的 `REVIEW_PRIORITY` 三級）。`plan` / `unmatched` 在「要你決定」、
 * `audit` / `duplicate` 在「等你看一眼」、`issue` 在「外面發生的事」。鍵取自列的聯集，所以後端多一類
 * 而這裡沒寫那一格時是 `tsc` 的事。
 */
const SECTION_OF: Record<ReviewKind, SectionName> = {
  plan: 'decide',
  unmatched: 'decide',
  audit: 'look',
  duplicate: 'look',
  issue: 'outside',
}

/**
 * 照後端的順序把列分進三段，段的順序是它第一次出現的順序。空的段自然不會出現。
 *
 * **按段名收，不按「連續的同一段」切**：`REVIEW_PRIORITY` 哪天讓兩類交錯的話，後者會切出兩個
 * 同名的段（重複的 `id` 與 `key`）。段內的順序仍然是後端給的那一份。
 */
function sections(rows: readonly ReviewRow[]) {
  const found = new Map<SectionName, ReviewRow[]>()
  for (const row of rows) {
    const name = SECTION_OF[row.kind]
    found.set(name, [...(found.get(name) ?? []), row])
  }
  return [...found].map(([name, grouped]) => ({ name, rows: grouped }))
}

/** 讀取中的佔位：兩列靜態方塊，沒有動畫（同 `/issues`）。 */
function Loading() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      <div className="h-24 border-2 border-rule bg-well" />
      <div className="h-24 border-2 border-rule bg-well" />
    </div>
  )
}

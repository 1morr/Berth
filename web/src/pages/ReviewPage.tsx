import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  reviewQueryOptions,
  type AuditReviewRow,
  type ReviewKind,
  type ReviewRow,
} from '../api/review'
import { PAGE_TITLE, TEXT_LINK } from '../components/controls'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { AuditGroup } from '../review/AuditGroup'
import { AuditSectionConfirm } from '../review/AuditSectionConfirm'
import { groupAudits, type ReviewEntry } from '../review/auditGroups'
import { ReviewItem } from '../review/ReviewItem'
import type { Said } from '../review/useConfirmAudits'

/**
 * 審核佇列 `/review`（`.scratch/m2/review-shape.md`，M2 票 06）。
 *
 * **一列一件事的清單，不是牆**（brief §13）：篩出來常常只有一兩件，卡片牆說不出「有幾件事在等你」。
 * 成功的樣子是空清單。
 *
 * **兩段，需要人動手的排前面**（使用者 2026-09-23 拍板）。後端已經照這個順序排好，這裡只是把
 * 連續的同一段切開、各給一條抬頭——**前端不重排**，排序只有後端一份。空的段不畫。
 *
 * **Issue 不在這一頁**（M3 票 05，brief §19 2026-09-24）：原本的第三段「外面發生的事」只剩一行
 * 「另有 N 件待處理」連到 `/issues`，0 件時不出現。這一頁是「入庫要人決定」，那一頁是「Berth 與
 * 外界對不上」。
 *
 * **同一個 Job 的 audit 收成一組**（`groupAudits`，一組一顆「全部確認」），audit 段的標題列另有一顆
 * 整段的（`AuditSectionConfirm`）。一次消失好幾列，所以那兩顆的結果看得見，不只念出來。
 */
export function ReviewPage() {
  const { t } = useTranslation()
  const queue = useQuery(reviewQueryOptions())
  // 按完那一列就消失了，焦點與畫面上都不剩任何東西說「成了」——這一句給看不見畫面的人。整組或整段
  // 一次消失時也給看得見的人（`shown`）：確認了幾個、跳過了幾個要對得上剛剛看到的列數。
  const [said, setSaid] = useState({ text: '', shown: false })
  const done: Said = (text, shown = false) => setSaid({ text, shown })
  const frame = useFocusAfterRemoval()

  return (
    <div ref={frame} className="mx-auto grid w-full max-w-[80rem] gap-6 px-6 py-8">
      <div className="grid gap-1 border-b-2 border-rule-strong pb-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 tabIndex={-1} className={PAGE_TITLE}>
            {t('review.title')}
          </h1>
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

      <p aria-live="polite" className={said.shown ? 'text-sm text-ink' : 'sr-only'}>
        {said.text}
      </p>

      {queue.isPending ? (
        <Loading />
      ) : !queue.data ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('review.off')}</p>
      ) : queue.data.rows.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('review.empty')}</p>
      ) : (
        sections(queue.data.rows).map((section) => {
          const audits = section.rows.filter((row): row is AuditReviewRow => row.kind === 'audit')
          const entries = groupAudits(section.rows)
          return (
            <section
              key={section.name}
              aria-labelledby={`review-${section.name}`}
              className="grid gap-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b-2 border-rule-strong pb-1.5">
                <h2
                  id={`review-${section.name}`}
                  className="flex flex-wrap items-baseline gap-x-2 self-center"
                >
                  <span className="label text-ink">{t(`review.section.${section.name}`)}</span>
                  <span className="value text-xs text-ink-dim">{section.rows.length}</span>
                </h2>
                {/* 整段確認只在它比一組多做了事的時候給：audit 全在同一組裡時，那一組的鍵就是它。 */}
                {audits.length > 1 && auditEntries(entries) > 1 && (
                  <AuditSectionConfirm rows={audits} onDone={done} />
                )}
              </div>
              <ul className="grid gap-3">
                {entries.map((entry) => (
                  <li key={entryKey(entry)} className="min-w-0">
                    {entry.kind === 'group' ? (
                      <AuditGroup rows={entry.rows} onDone={done} />
                    ) : (
                      <ReviewItem row={entry.row} onDone={done} />
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )
        })
      )}

      {queue.data && queue.data.issues_open > 0 && (
        <p className="text-sm text-ink-dim">
          <Link to="/issues" className={TEXT_LINK}>
            {t('review.issues', { count: queue.data.issues_open })}
          </Link>
        </p>
      )}
    </div>
  )
}

type SectionName = 'decide' | 'look'

/**
 * 每一類落在哪一段（plan §6 的 `REVIEW_PRIORITY` 兩級）。`plan` / `unmatched` 在「要你決定」、
 * `audit` / `duplicate` 在「等你看一眼」。鍵取自列的聯集，所以後端多一類而這裡沒寫那一格時是
 * `tsc` 的事。
 */
const SECTION_OF: Record<ReviewKind, SectionName> = {
  plan: 'decide',
  unmatched: 'decide',
  audit: 'look',
  duplicate: 'look',
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

/** 畫成幾格 audit：一組算一格。 */
function auditEntries(entries: readonly ReviewEntry[]) {
  return entries.filter((entry) => entry.kind === 'group' || entry.row.kind === 'audit').length
}

function entryKey(entry: ReviewEntry) {
  return entry.kind === 'group' ? entry.key : `${entry.row.kind}:${entry.row.ref}`
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

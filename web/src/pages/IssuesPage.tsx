import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { issuesQueryOptions, reconcileQueryOptions } from '../api/issues'
import { PAGE_TITLE } from '../components/controls'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { IssueRow } from '../issues/IssueRow'
import { ReconcileBanner } from '../issues/ReconcileBanner'

/**
 * 待處理頁 `/issues`（`.scratch/m2/issues-shape.md`，M2 票 05）。
 *
 * **獨立的一頁而不是健康頁的一段**（plan §11.3 決定 3）：健康頁是唯讀診斷，這一頁要按動作。
 *
 * 使用者是被一件壞掉的事叫來的——Jellyfin 裡刪了一部片、硬碟搬過家。他要做的是對每一件做
 * 一個決定，然後讓它從清單上消失。所以**成功的樣子是空清單**，而空的時候這一頁說的是
 * 「都對得上」，不是「沒有資料」。
 *
 * 不分頁、不篩選、不排序（同 `GET /review` 的決定）：這一票只有一種型別而清單很短；
 * 一次掛載掉了會讓整個媒體庫上榜，但那時候該修的是掛載，不是加一個分頁器。
 */
export function IssuesPage() {
  const { t } = useTranslation()
  const issues = useQuery(issuesQueryOptions())
  const reconcile = useQuery(reconcileQueryOptions())
  const frame = useFocusAfterRemoval()

  return (
    <div ref={frame} className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h1 tabIndex={-1} className={PAGE_TITLE}>
          {t('issues.title')}
        </h1>
        {issues.data && issues.data.length > 0 && (
          <p className="value text-xs text-ink-dim">
            {t('issues.count', { count: issues.data.length })}
          </p>
        )}
      </div>

      <ReconcileBanner />

      {issues.isPending ? (
        <Loading />
      ) : !issues.data ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('issues.off')}</p>
      ) : issues.data.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">
          {reconcile.data?.last ? t('issues.empty') : t('issues.emptyNeverRun')}
        </p>
      ) : (
        <ul className="grid gap-3">
          {issues.data.map((issue) => (
            <li key={issue.id} className="min-w-0">
              <IssueRow issue={issue} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * 讀取中的佔位。**兩列靜態方塊，沒有動畫**——這個世界沒有骨架屏的脈動（DESIGN.md）。
 *
 * 高度與真的一列相近，資料回來時版面不跳（票 12 的 CLS 是同一件事）。
 */
function Loading() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      <div className="h-24 border-2 border-rule bg-well" />
      <div className="h-24 border-2 border-rule bg-well" />
    </div>
  )
}

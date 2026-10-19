import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { releaseItem, RSS_KEY, type FeedItem } from '../api/rss'
import { COMPACT_BUTTON } from '../components/controls'
import { Dot } from '../components/Dot'
import { episodeCode } from '../components/episodes'
import { whenText } from '../components/queueText'
import { SIGNAL_FILL } from '../components/signal'
import { JobLink } from '../jobs/JobLink'
import { rssProblem } from './rssProblem'
import { skipText } from './skip'

/**
 * 一筆 Feed Item：狀態色塊、發佈名、集數、發佈時間、送出去的那一筆 Job、為什麼沒下載。
 *
 * 「最近的 Feed Item」與 RSS Series 展開的清單（M4 票 13）共用；前者多一行 `source`（來自哪個 Feed、
 * 屬於哪個 Series），後者整份都是同一個 Series，不說。放在 `gap-px bg-rule` 的 `ul` 裡。
 */
export function ItemLine({ row, source }: { row: FeedItem; source?: ReactNode }) {
  const { t, i18n } = useTranslation()

  return (
    <li className="grid min-w-0 gap-1 bg-well px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <ItemChip row={row} />
        <span className="value min-w-0 basis-full text-sm wrap-anywhere text-ink sm:flex-1 sm:basis-auto">
          {row.title}
        </span>
      </div>
      <p className="text-xs text-ink-dim">
        {row.episode !== null && (
          <>
            <span className="value text-ink">{episodeCode(row.episode)}</span> <Dot />{' '}
          </>
        )}
        {t('rss.items.published')}{' '}
        <span className="value">
          {row.published_at ? whenText(row.published_at, i18n.language) : '—'}
        </span>
        {row.job_hash && (
          <>
            {' '}
            <Dot /> <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
          </>
        )}
      </p>
      {source && <p className="text-xs wrap-anywhere text-ink-dim">{source}</p>}
      {/* 排除與去重擋下的都不是錯誤（票 10）：一句「為什麼沒下載」，不塗漆。 */}
      {row.skip && (
        <p className="max-w-prose text-xs wrap-anywhere text-ink-dim">{skipText(t, row.skip)}</p>
      )}
      {row.status === 'excluded' && <Release row={row} />}
      {row.error && (
        <p className="value text-xs wrap-anywhere text-ink">
          {row.status === 'excluded' && <>{t('rss.items.releaseFailed')} </>}
          {row.error}
        </p>
      )}
    </li>
  )
}

/**
 * 「仍然下載」（M4 票 111）：被排除的那一筆逐筆放行，當場送出。送出之後三份清單一起重問，這一列就換成
 * 送出去的 Job（或重複的理由）；送單被拒時它留在排除，原文在 `error`。
 *
 * 放行不了時（還沒綁定、還在預覽）照後端的 `release_blocked` 停用並說原因。用 `aria-disabled` 不用
 * `disabled`：停用的那一顆仍接得住焦點，原因由 `aria-describedby` 念出來（DESIGN.md 送出中同理）。
 */
function Release({ row }: { row: FeedItem }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const whyId = useId()
  const release = useMutation({
    mutationFn: () => releaseItem(row.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RSS_KEY }),
  })
  const blocked = row.release_blocked
  const locked = blocked !== null || release.isPending

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <button
        type="button"
        className={`${COMPACT_BUTTON} aria-disabled:cursor-not-allowed`}
        aria-disabled={locked || undefined}
        aria-describedby={blocked !== null ? whyId : undefined}
        onClick={() => {
          if (!locked) release.mutate()
        }}
      >
        {release.isPending ? t('rss.items.releasing') : t('rss.items.release')}
      </button>
      {blocked !== null && (
        <p id={whyId} className="max-w-prose text-xs text-ink-dim">
          {t(`rss.refusal.${blocked}`)}
        </p>
      )}
      {release.isError && (
        <p role="alert" className="max-w-prose text-xs wrap-anywhere text-ink">
          {rssProblem(t, release.error)}
        </p>
      )}
    </div>
  )
}

/**
 * 一筆 Item 的狀態色塊。**常態不塗漆**：待綁定已經在第一段塗過了，已送單是沒事，已排除與重複是
 * 照使用者的規則與帳本擋下的（票 10，不是錯誤）；只有送不出去
 * （`matched` 帶著原文）塗 `assigned`——卡住了、下一輪會再送，但原因（Route 紅燈、磁碟門檻）
 * 多半要人去修（DESIGN.md：卡住是 `assigned`，`blocked` 留給失敗）。
 */
function ItemChip({ row }: { row: FeedItem }) {
  const { t } = useTranslation()
  const stuck = row.status === 'matched' && row.error !== ''
  const key = stuck ? 'stuck' : row.status
  return (
    <span className={`label px-1.5 py-0.5 ${stuck ? SIGNAL_FILL.assigned : SIGNAL_FILL.neutral}`}>
      {t(`rss.items.status.${key}`)}
    </span>
  )
}

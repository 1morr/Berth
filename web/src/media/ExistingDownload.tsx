import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { oneshotQueryOptions, parseRssRefusal } from '../api/rss'
import { GhostButton, Notice } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { OneshotList } from '../rss/OneshotList'

/** 「只下載現有的」要讀的那一條：番組 × 字幕組的單一 feed（後端給的網址）與送到的 Route。 */
export interface ExistingTarget {
  url: string
  route: number
}

/**
 * 作品頁的「只下載現有的」（M4 票 112）：一顆展開鍵，展開後就地讀一次那個字幕組的單一 feed，列出
 * 與 /rss 一次性連結同一份勾選清單（`OneshotList`）。作品是這一頁的，Route 是訂閱那裡選的；
 * 不建 Feed，逐筆走一般送單（`trigger = manual`），合集照樣勾得了（排除條件只管自動下載）。
 *
 * 給已經完結、字幕組只出合集的作品：訂閱建的 Feed 擋下合集，之後也不會再有新的。
 */
export function ExistingDownload({ media, target }: { media: Media; target: ExistingTarget }) {
  const { t } = useTranslation()
  const listId = useId()
  const [open, setOpen] = useState(false)

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <GhostButton
          type="button"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          onClick={() => setOpen((before) => !before)}
        >
          {t('rss.subscribe.existing.open')}
        </GhostButton>
        <p className="max-w-prose text-xs text-ink-dim">{t('rss.subscribe.existing.hint')}</p>
      </div>
      {open && (
        <div id={listId} className="grid gap-3">
          <Listing media={media} target={target} />
        </div>
      )}
    </div>
  )
}

function Listing({ media, target }: { media: Media; target: ExistingTarget }) {
  const { t } = useTranslation()
  const read = useQuery({
    ...oneshotQueryOptions(target.url, media.id, target.route),
    // 換了 Route 時重讀的那幾秒清單不消失（同 /rss 的一次性連結）。
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === target.url ? previous : undefined,
  })

  if (read.data) {
    // 換一條網址就是另一批：勾選與結果從頭來。
    return <OneshotList key={target.url} read={read.data} media={media} route={target.route} />
  }
  if (read.isError) {
    const refusal = parseRssRefusal(read.error)
    if (refusal === null) return <RequestFailed error={read.error} lead={t('request.notDone')} />
    return (
      <Notice signal="blocked" label={t('common.failed')}>
        {refusal.reason === 'feed_unreachable'
          ? t('rss.subscribe.existing.unreachable')
          : t(`rss.refusal.${refusal.reason}`)}
        {refusal.detail ? (
          <span className="value block text-xs wrap-anywhere">{refusal.detail}</span>
        ) : null}
        <span className="mt-2 block">
          <GhostButton type="button" busy={read.isFetching} onClick={() => void read.refetch()}>
            {t('rss.subscribe.existing.retry')}
          </GhostButton>
        </span>
      </Notice>
    )
  }
  return <p className="text-xs text-ink-dim">{t('rss.subscribe.existing.reading')}</p>
}

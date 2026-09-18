import { useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { accessRefusal, type JellyfinWeb } from '../api/jellyfin'
import {
  homeWatchingQueryOptions,
  libraryWatchingQueryOptions,
  type Watching,
  type WatchingCard,
} from '../api/watching'
import { ArtSlot } from '../components/ArtSlot'
import { COMPACT_BUTTON, GhostButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { formatJellyfinEpisode } from '../components/episodes'
import { KIND_CODE } from '../components/kind'
import { SessionEnded } from '../components/SessionEnded'
import { WALL_GRID, fitsOneRowFrom, oneRowOnly } from '../discover/wallGrid'
import { jellyfinDetailsUrl } from '../inventory/jellyfinLink'

/**
 * 首頁上方的兩列（M1.5 票 07、`.scratch/m1.5/watching-shape.md`）：這個人整個帳號的繼續觀看與下一集。
 *
 * 讀取中不畫、沒有內容的那一列不畫（多數時候是空的，先畫格子再整列消失比晚一點出現更跳）。問不到 Jellyfin
 * 時說一行、給重試，不用紅色 Notice 搶探索的位置；Berth 自己沒回應時不說話，探索牆會說。
 */
export function HomeWatching() {
  const { t } = useTranslation()
  const watching = useQuery(homeWatchingQueryOptions)
  const refusal = accessRefusal(watching.error)

  if (watching.data) return <WatchingRows watching={watching.data} />
  if (watching.error instanceof ApiError && watching.error.status === 401) {
    return <SessionEnded pending={null} />
  }
  if (refusal?.reason !== 'jellyfin_unreachable') return null

  return (
    <div className="grid justify-items-start gap-2">
      <p className="max-w-prose text-sm text-ink-dim">{t('watching.down')}</p>
      {refusal.detail && (
        <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
      )}
      <GhostButton type="button" onClick={() => void watching.refetch()}>
        {t('watching.retry')}
      </GhostButton>
    </div>
  )
}

/**
 * 媒體庫頁上方的兩列：只含這個媒體庫的。拒絕與錯誤一律不畫——牆那一塊會說原因，同一件事不說兩次。
 */
export function LibraryWatching({ libraryId }: { libraryId: string }) {
  const watching = useQuery(libraryWatchingQueryOptions(libraryId))
  return watching.data ? <WatchingRows watching={watching.data} /> : null
}

function WatchingRows({ watching }: { watching: Watching }) {
  const { t } = useTranslation()

  return (
    <>
      {watching.resume.length > 0 && (
        <WatchingRow
          title={t('watching.resume')}
          cards={watching.resume}
          web={watching.jellyfin}
          progress
        />
      )}
      {watching.next_up.length > 0 && (
        <WatchingRow
          title={t('watching.nextUp')}
          cards={watching.next_up}
          web={watching.jellyfin}
        />
      )}
    </>
  )
}

function WatchingRow({
  title,
  cards,
  web,
  progress = false,
}: {
  title: string
  cards: WatchingCard[]
  web: JellyfinWeb
  /** 繼續觀看那一列說看到幾 %；下一集那一列沒有。 */
  progress?: boolean
}) {
  const { t } = useTranslation()
  const headingId = useId()
  const listId = useId()
  const [expanded, setExpanded] = useState(false)
  // 一行、多的就地展開（使用者拍板）：收起時每一格帶「哪個寬度以上才出現」，一份 DOM、不量寬度。
  const fits = fitsOneRowFrom(cards.length)

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {title}
        </h2>
        {/* 光一個數字唸出來沒有意義：看得見的是數字，聽得見的是帶單位的那一句。 */}
        <p className="value text-xs text-ink-dim">
          <span aria-hidden="true">{cards.length}</span>
          <span className="sr-only">{t('watching.count', { count: cards.length })}</span>
        </p>
        {fits !== null && (
          // 開關在標題列而不是清單下方：展開之後下一個 Tab 從第一格往下走，新出現的格子不會落在焦點後面。
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={listId}
            onClick={() => setExpanded(!expanded)}
            className={`${COMPACT_BUTTON} ms-auto ${fits}`}
          >
            {expanded ? t('watching.showFewer') : t('watching.showAll', { count: cards.length })}
          </button>
        )}
      </div>
      <ul id={listId} className={WALL_GRID}>
        {cards.map((card, index) => (
          <li key={card.item_id} className={expanded ? '' : oneRowOnly(index)}>
            <WatchingTile card={card} web={web} progress={progress} />
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * 橫放的貨櫃：16:9 的圖是塗裝，下面是同一條標識帶。**整格是一條連結**，開 Jellyfin 那一集（或那部電影）的
 * 詳細頁——Jellyfin 沒有直接開始播放的網址，使用者在那裡再按一次播放（研究 §8）。
 */
function WatchingTile({
  card,
  web,
  progress,
}: {
  card: WatchingCard
  web: JellyfinWeb
  progress: boolean
}) {
  const { t } = useTranslation()
  const url = jellyfinDetailsUrl(web, card.item_id, window.location)
  const frame = 'grid h-full grid-rows-[auto_1fr] border-2 border-rule bg-well'

  const body = (
    <>
      <ArtSlot url={card.image_url} shape="wide" />
      <div className="grid content-start gap-1 px-3 py-2.5">
        <p className="value min-h-4 text-xs text-ink-dim">
          {card.kind === 'movie' ? (
            <>
              {KIND_CODE.movie} <Dot /> {card.year ?? '—'}
            </>
          ) : (
            formatJellyfinEpisode(card)
          )}
        </p>
        <p className="value line-clamp-1 text-sm text-ink">{card.title}</p>
        <p className="value line-clamp-1 min-h-4 text-xs text-ink-dim">{card.episode_name}</p>
        {progress && card.progress !== null && (
          <p className="value text-xs text-ink">
            {t('inventory.watch.progress', { progress: card.progress })}
          </p>
        )}
        {url ? (
          <span className="sr-only">{t('inventory.jellyfin.newTab')}</span>
        ) : (
          <p className="text-xs text-ink">{t('inventory.jellyfin.noAddress')}</p>
        )}
      </div>
    </>
  )

  if (!url) return <div className={frame}>{body}</div>
  return (
    <a href={url} target="_blank" rel="noreferrer" className={`${frame} hover:border-rule-strong`}>
      {body}
    </a>
  )
}

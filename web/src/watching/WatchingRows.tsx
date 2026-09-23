import { useEffect, useId, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
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
import { PlaceholderLine } from '../components/TilePlaceholder'
import { WALL_GRID, fitsOneRowFrom, oneRowOnly } from '../components/wallGrid'
import { jellyfinDetailsUrl } from '../inventory/jellyfinLink'
import { rememberRows, rememberedRows, type RowShape } from './rememberedRows'

/**
 * 首頁上方的兩列（M1.5 票 07、`.scratch/m1.5/watching-shape.md`）：這個人整個帳號的繼續觀看與下一集。
 *
 * 沒有內容的那一列不畫。**讀取中照上一次的形狀佔位**（M2 票 13，推翻 watching-shape 的「讀取中不畫」：
 * 資料回來才插進來，下面整頁往下推 440px，CLS 0.35）；第一次來沒有紀錄，不佔位（`rememberedRows`）。
 * 問不到 Jellyfin 時說一行、給重試，不用紅色 Notice 搶探索的位置；Berth 自己沒回應時不說話，探索牆會說。
 */
export function HomeWatching() {
  const { t } = useTranslation()
  const watching = useQuery(homeWatchingQueryOptions)
  const refusal = accessRefusal(watching.error)
  const shape = useRememberedRows('home', watching.data)

  if (watching.data) return <WatchingRows watching={watching.data} />
  if (watching.isPending) return <WatchingPlaceholder shape={shape} />
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
  const shape = useRememberedRows(`library.${libraryId}`, watching.data)

  if (watching.data) return <WatchingRows watching={watching.data} />
  return watching.isPending ? <WatchingPlaceholder shape={shape} /> : null
}

/**
 * 媒體庫頁翻頁、篩選時那兩列收起（使用者拍板，票 07）；這一行說它們去了哪裡、給一條回去的路（票 13）。
 *
 * **只在上一次真的有東西可接著看時說**：那兩列在這些時候不問 Jellyfin，所以只有上一次的形狀可依據——
 * 從來沒看過任何東西的人翻到第 2 頁，不該多一行說一件與他無關的事。`children` 是回第 1 頁的連結。
 */
export function WatchingElsewhere({
  libraryId,
  children,
}: {
  libraryId: string
  children: ReactNode
}) {
  const { t } = useTranslation()
  const shape = useLastShape(useRowsKey(`library.${libraryId}`))
  if (!shape || shape.resume + shape.nextUp === 0) return null

  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-dim">
      <span>{t('watching.elsewhere')}</span>
      {children}
    </p>
  )
}

/** 紀錄以登入的人區分：同一台瀏覽器換人登入，不拿上一個人的形狀。 */
function useRowsKey(page: string): string | null {
  const me = useQuery(meQueryOptions)
  return me.data ? `${me.data.name}.${page}` : null
}

/** 這個人在這一頁上一次的形狀，資料到了就記下這一次的。 */
function useRememberedRows(page: string, watching: Watching | undefined): RowShape | null {
  const key = useRowsKey(page)

  useEffect(() => {
    if (key && watching) rememberRows(key, watching)
  }, [key, watching])

  return useLastShape(key)
}

/** 上一次的形狀。只在第一次畫的那一刻讀：之後這一頁自己就知道形狀了。 */
function useLastShape(key: string | null): RowShape | null {
  const [shape] = useState(() => (key ? rememberedRows(key) : null))
  return shape
}

/**
 * 讀取中：照上一次的形狀，每一列一個標題列與一行不動的空位格（`MediaDetailPage` 的 `Loading()` 那一種，
 * 不是骨架屏動畫）。**高度與真的那一列一樣**：標題列的「全部 N 項」照上一次的格數決定畫不畫（看不見但佔位），
 * 空位格照 `WatchingTile` 的每一行抄。整塊不在無障礙樹上——標題是真的，但底下什麼都還沒有。
 */
function WatchingPlaceholder({ shape }: { shape: RowShape | null }) {
  const { t } = useTranslation()
  if (!shape) return null

  return (
    <>
      {shape.resume > 0 && (
        <RowPlaceholder title={t('watching.resume')} count={shape.resume} progress />
      )}
      {shape.nextUp > 0 && <RowPlaceholder title={t('watching.nextUp')} count={shape.nextUp} />}
    </>
  )
}

function RowPlaceholder({
  title,
  count,
  progress = false,
}: {
  title: string
  count: number
  progress?: boolean
}) {
  const { t } = useTranslation()
  const fits = fitsOneRowFrom(count)

  return (
    <div aria-hidden="true" data-placeholder="watching" className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <p className="label text-ink">{title}</p>
        {/* 數字還不知道，但它那一行撐著標題列的高度。 */}
        <p className="value invisible text-xs">{count}</p>
        {fits !== null && (
          <span className={`${COMPACT_BUTTON} invisible ms-auto ${fits}`}>
            {t('watching.showAll', { count })}
          </span>
        )}
      </div>
      <div className={WALL_GRID}>
        {Array.from({ length: Math.min(count, 6) }, (_, index) => (
          <div
            key={index}
            className={`grid grid-rows-[auto_1fr] border-2 border-rule bg-well ${oneRowOnly(index)}`}
          >
            <div className="aspect-video bg-hull" />
            <div className="grid content-start gap-1 px-3 py-2.5">
              <PlaceholderLine className="h-4 w-12" />
              <PlaceholderLine className="h-5 w-4/5" />
              <PlaceholderLine className="h-4 w-1/2" />
              {progress && <PlaceholderLine className="h-4 w-1/3" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
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
  const progressId = useId()
  const percent = progress ? card.progress : null
  // 名字從作品名念起（票 13）：整格的字串起來是「無圖 S01E04 …」。集號與集名跟在後面，才分得出是哪一集。
  const name = [
    card.title,
    card.kind === 'movie' ? '' : formatJellyfinEpisode(card),
    card.episode_name ?? '',
  ]
    .filter(Boolean)
    .join(' ')

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
        <h3 className="value line-clamp-1 text-sm text-ink">{card.title}</h3>
        <p className="value line-clamp-1 min-h-4 text-xs text-ink-dim">{card.episode_name}</p>
        {percent !== null && (
          <p id={progressId} className="value text-xs text-ink">
            {t('inventory.watch.progress', { progress: percent })}
          </p>
        )}
        {!url && <p className="text-xs text-ink">{t('inventory.jellyfin.noAddress')}</p>}
      </div>
    </>
  )

  if (!url) return <div className={frame}>{body}</div>
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={t('inventory.jellyfin.itemNewTab', { name })}
      aria-describedby={percent !== null ? progressId : undefined}
      className={`${frame} hover:border-rule-strong`}
    >
      {body}
    </a>
  )
}

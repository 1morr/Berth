import { useId, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { WatchState } from '../api/jellyfin'
import {
  episodesKey,
  episodesQueryOptions,
  watchKey,
  type WatchArea,
  type WatchEpisode,
  type WatchSeason,
} from '../api/media'
import {
  GhostButton,
  NAV_BOX,
  NAV_BOX_ACTIVE,
  PRIMARY_LINK,
  TEXT_LINK,
} from '../components/controls'
import { formatJellyfinEpisode } from '../components/episodes'
import { Tile } from '../components/Tile'
import { WatchToggle } from '../components/WatchToggle'
import { watchLine } from '../components/watchLine'
import { WALL_GRID, oneRowOnly } from '../components/wallGrid'
import { jellyfinDetailsUrl } from '../inventory/jellyfinLink'

/**
 * Media 詳情的觀看區（M1.5 票 08、`.scratch/m1.5/media-detail-shape.md`）：作品在 Jellyfin 裡、這個人看得到
 * 時才有。兩塊，住在頁面上兩個位置：
 *
 * - **主按鈕**（`CarryOn`）在身分帶裡：這部劇接下來看哪一集（Jellyfin 的 NextUp），電影就是這一部。
 * - **觀看**（`WatchSection`）是身分帶底下第一個區塊：Jellyfin 的季切換加那一季的集。
 *
 * 資料原樣來自 Jellyfin，季名與集名是它的，不疊 Berth 的入庫狀態（那是下面「季集與入庫」的事）。
 * 按下去一律開 Jellyfin 那一項的詳細頁、新分頁——Jellyfin 沒有直接開始播放的網址（研究 §8）。
 */

/** 身分帶裡的主按鈕與它下面那一行。電影的「標為已看 / 未看」也在這裡（電影沒有觀看區）。 */
export function CarryOn({ mediaId, area }: { mediaId: string; area: WatchArea }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const lineId = useId()
  const episode = area.carry_on
  const target = episode ? episode.item_id : area.item_id
  const url = jellyfinDetailsUrl(area.jellyfin, target, window.location)
  const label = carryOnLabel(area)
  // 劇集沒有下一集不一定是看完了：只剩 Specials 或缺片時 NextUp 也回空（研究 §7.3），那時不說話。
  const line = episode
    ? [episode.name, watchLine(t, episode.watch)].filter(Boolean).join(' · ')
    : area.kind === 'tv'
      ? area.watch.played
        ? t('watch.allWatched')
        : ''
      : watchLine(t, area.watch)

  return (
    // 下面那一行貼著主按鈕（它說的是那一集）；電影的切換鍵在旁邊，窄版換到下一行。
    <div className="flex flex-wrap items-start gap-3">
      <div className="grid w-full gap-2 sm:w-auto">
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            aria-describedby={line ? lineId : undefined}
            className={`${PRIMARY_LINK} sm:min-w-64`}
          >
            {t(label.key, label.values)}
            <span className="sr-only">{t('inventory.jellyfin.newTab')}</span>
          </a>
        ) : (
          <p className="text-sm text-ink">{t('inventory.jellyfin.noAddress')}</p>
        )}
        {line && (
          <p id={lineId} className="value text-xs text-ink">
            {line}
          </p>
        )}
      </div>
      {area.kind === 'movie' && (
        <WatchToggle
          itemId={area.item_id}
          target="movie"
          watch={area.watch}
          describedBy={line ? lineId : undefined}
          onWritten={(written) =>
            queryClient.setQueryData<WatchArea | null>(watchKey(mediaId), (data) =>
              data ? { ...data, watch: written } : data,
            )
          }
        />
      )}
    </div>
  )
}

/**
 * 主按鈕上那一句：看到一半的集是「繼續看」、第一季第一集是「從那一集開始看」、其餘是「看下一集」；
 * 劇集看完了、或電影，就是開那一部。哪一集由 Jellyfin 算（NextUp），這裡只挑說法。
 */
function carryOnLabel(area: WatchArea) {
  const episode = area.carry_on
  if (!episode) {
    if (area.kind === 'tv') return { key: 'watch.open' } as const
    return { key: area.watch.progress === null ? 'watch.film' : 'watch.filmResume' } as const
  }
  const code = formatJellyfinEpisode(episode)
  if (episode.watch.progress !== null) return { key: 'watch.resume', values: { code } } as const
  if (episode.season === 1 && episode.episode_start === 1) {
    return { key: 'watch.first', values: { code } } as const
  }
  return { key: 'watch.next', values: { code } } as const
}

/**
 * 身分帶底下第一個區塊：季切換與那一季的集（橫卡，與首頁「繼續觀看」同一種、同一份 `WALL_GRID`）。
 * 電影沒有這一區。
 */
export function WatchSection({ mediaId, area }: { mediaId: string; area: WatchArea }) {
  const { t } = useTranslation()
  const headingId = useId()
  // 預設是主按鈕那一集所在的季；之後就是使用者選的那一季。**只在第一次決定**：標為已看之後主按鈕換成
  // 下一季的第一集時，眼前這一季不該跟著跳走。
  const [seasonId, setSeasonId] = useState(() => defaultSeason(area)?.id ?? null)
  const seriesUrl = jellyfinDetailsUrl(area.jellyfin, area.item_id, window.location)
  const remaining = area.watch.played
    ? t('watch.allWatched')
    : area.watch.unplayed_episodes !== null
      ? t('inventory.watch.unplayed', { count: area.watch.unplayed_episodes })
      : ''

  return (
    <section aria-labelledby={headingId} className="grid gap-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {t('watch.title')}
        </h2>
        {remaining && <p className="value text-xs text-ink-dim">{remaining}</p>}
        {seriesUrl && (
          <a href={seriesUrl} target="_blank" rel="noreferrer" className={`${TEXT_LINK} ms-auto`}>
            {t('watch.open')}
            <span className="sr-only">{t('inventory.jellyfin.newTab')}</span>
          </a>
        )}
      </div>

      {area.seasons.length === 0 || seasonId === null ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('watch.noSeasons')}</p>
      ) : (
        <>
          {area.seasons.length > 1 && (
            <SeasonSwitch seasons={area.seasons} chosen={seasonId} onChoose={setSeasonId} />
          )}
          <Episodes mediaId={mediaId} area={area} seasonId={seasonId} />
        </>
      )}
    </section>
  )
}

function defaultSeason(area: WatchArea): WatchSeason | undefined {
  const season = area.carry_on?.season
  return (
    area.seasons.find((row) => season != null && row.number === season) ??
    area.seasons.find((row) => row.number !== null && row.number > 0) ??
    area.seasons[0]
  )
}

/**
 * 一排導覽方塊（媒體庫切換列的同一種），選中的那一個重線 + `deck` 底。**是按鈕不是連結**：季不在網址上
 * （shape §4），`aria-pressed` 說哪一個選著。35 季就換行，不橫向捲動。
 */
function SeasonSwitch({
  seasons,
  chosen,
  onChoose,
}: {
  seasons: readonly WatchSeason[]
  chosen: string
  onChoose: (id: string) => void
}) {
  const { t } = useTranslation()

  return (
    <div role="group" aria-label={t('watch.seasons')} className="flex flex-wrap gap-2">
      {seasons.map((season) => (
        <button
          key={season.id}
          type="button"
          aria-pressed={season.id === chosen}
          onClick={() => onChoose(season.id)}
          className={`${season.id === chosen ? NAV_BOX_ACTIVE : NAV_BOX} inline-flex min-h-6 items-center px-3 py-1.5 text-ink`}
        >
          {season.name}
        </button>
      ))}
    </div>
  )
}

function Episodes({
  mediaId,
  area,
  seasonId,
}: {
  mediaId: string
  area: WatchArea
  seasonId: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const episodes = useQuery(episodesQueryOptions(area.item_id, seasonId))

  if (episodes.isPending) {
    // 不動的空位格，一行（不是骨架屏動畫）。
    return (
      <ul className={WALL_GRID} aria-hidden="true">
        {Array.from({ length: 6 }, (_, index) => (
          <li key={index} className={oneRowOnly(index)}>
            <div className="aspect-video border-2 border-rule bg-deck" />
          </li>
        ))}
      </ul>
    )
  }
  if (episodes.isError) {
    return <RetryLine message={t('watch.failed')} onRetry={() => void episodes.refetch()} />
  }
  if (episodes.data.length === 0) {
    return <p className="max-w-prose text-sm text-ink-dim">{t('watch.emptySeason')}</p>
  }

  const onWritten = (itemId: string, written: WatchState) => {
    // 那一格就地換；主按鈕與「剩幾集沒看」重問一次（下一集可能換了），它們在上面、位置不動。
    queryClient.setQueryData<WatchEpisode[]>(episodesKey(area.item_id, seasonId), (rows) =>
      rows?.map((row) => (row.item_id === itemId ? { ...row, watch: written } : row)),
    )
    void queryClient.invalidateQueries({ queryKey: watchKey(mediaId) })
  }

  return (
    <ul className={WALL_GRID} aria-busy={episodes.isPlaceholderData || undefined}>
      {episodes.data.map((episode) => (
        <li key={episode.item_id} className="min-w-0">
          <EpisodeTile
            episode={episode}
            area={area}
            onWritten={(written) => onWritten(episode.item_id, written)}
          />
        </li>
      ))}
    </ul>
  )
}

/**
 * 一集：橫放的貨櫃（首頁那兩列的同一種）。外框、圖與底行是 `Tile`（與媒體庫牆的卡片同一份，M2 票 14）：上面那一塊
 * 是一條連結，開 Jellyfin 那一集、新分頁；最下面一行是「標為已看 / 未看」——兩者並排不巢狀。
 */
function EpisodeTile({
  episode,
  area,
  onWritten,
}: {
  episode: WatchEpisode
  area: WatchArea
  onWritten: (written: WatchState) => void
}) {
  const { t } = useTranslation()
  const url = jellyfinDetailsUrl(area.jellyfin, episode.item_id, window.location)
  const upNext = area.carry_on?.item_id === episode.item_id
  const lineId = useId()
  // 集名可能是空的或只是「Episode 4」：名字帶上集號才分得出是哪一集（票 13）。整格的字串起來是
  // 「無圖 S01E04 …」，所以連結與「標為已看」都用這一個名字，不讓圖位的字進來。
  const name = [formatJellyfinEpisode(episode), episode.name].filter(Boolean).join(' ')

  return (
    <Tile
      art={episode.still_url}
      shape="wide"
      link={url ? { href: url } : null}
      label={t('inventory.jellyfin.itemNewTab', { name })}
      describedBy={lineId}
      foot={
        <WatchToggle
          itemId={episode.item_id}
          target="episode"
          watch={episode.watch}
          subject={name}
          onWritten={onWritten}
        />
      }
    >
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="value text-xs text-ink-dim">{formatJellyfinEpisode(episode)}</span>
        {upNext && (
          // 中性小色塊：「接下來看這一集」是一個位置，不是四個信號色裡的任何一個狀態。
          <span className="label bg-deck px-1.5 py-0.5 text-ink">
            {episode.watch.progress === null ? t('watch.chipNext') : t('watch.chipResume')}
          </span>
        )}
      </p>
      <h3 className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">{episode.name}</h3>
      <p id={lineId} className="value min-h-4 text-xs text-ink">
        {watchLine(t, episode.watch)}
      </p>
      {!url && <p className="text-xs text-ink">{t('inventory.jellyfin.noAddress')}</p>}
    </Tile>
  )
}

/**
 * 問不到 Jellyfin：觀看區的位置換成一行字與重試（首頁那一列的形狀），不用紅色 Notice——搜尋與下面的一切
 * 照樣能用。
 */
export function WatchDown({ detail, onRetry }: { detail: string; onRetry: () => void }) {
  const { t } = useTranslation()
  return <RetryLine message={t('watch.down')} detail={detail} onRetry={onRetry} />
}

/** 一行 `ink-dim` 的原因、服務原文（有的話）與 Ghost「重試」：觀看區讀不到東西時只有這一種樣子。 */
function RetryLine({
  message,
  detail = '',
  onRetry,
}: {
  message: string
  detail?: string
  onRetry: () => void
}) {
  const { t } = useTranslation()

  return (
    <div className="grid justify-items-start gap-2">
      <p className="max-w-prose text-sm text-ink-dim">{message}</p>
      {detail && <p className="value text-xs wrap-anywhere text-ink-dim">{detail}</p>}
      <GhostButton type="button" onClick={onRetry}>
        {t('watch.retry')}
      </GhostButton>
    </div>
  )
}

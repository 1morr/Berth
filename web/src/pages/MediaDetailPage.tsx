import { useRef, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { accessRefusal } from '../api/jellyfin'
import { meQueryOptions } from '../api/auth'
import { mediaQueryOptions, refresh, watchQueryOptions, type Media } from '../api/media'
import { GHOST_LINK, GhostButton, Notice } from '../components/controls'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { Timestamp } from '../components/Timestamp'
import { TmdbNotice } from '../components/TmdbNotice'
import { displayRound } from '../i18n/displayRound'
import { FilesPanel } from '../media/FilesPanel'
import { SearchPanel, type SearchHandle } from '../media/SearchPanel'
import { SeasonsPanel } from '../media/SeasonsPanel'
import { CarryOn, WatchDown, WatchSection } from '../media/WatchArea'
import { TmdbAttribution } from '../components/TmdbAttribution'
import { ArtSlot } from '../components/ArtSlot'

/**
 * Media 詳情頁 `/media/:id`（票 04、M1.5 票 08、`.scratch/m1.5/media-detail-shape.md`）。
 *
 * 探索與媒體庫點進的是**同一頁**（brief §13）。兩個時刻共用它：「我要看這部」與「這是不是我要的、要不要下載」。
 * 所以頁面分兩層（使用者 2026-09-18 拍板）：
 *
 * 1. **身分帶**：海報、標題、一行識別值、**主按鈕**（作品在 Jellyfin 裡時才有）、簡介、快照新鮮度。
 * 2. **觀看**：Jellyfin 的季與集（劇集在 Jellyfin 裡、這個人看得到時才有）。
 * 3. 以下是 Berth 的那一半，順序固定：**搜尋** → **季集與入庫** → **檔案與版本** → TMDB 標示。
 *
 * 不在 Jellyfin（或看不到）時少了主按鈕與觀看區，搜尋就排在身分帶正下方——原本的五列識別剖面把「搜尋」壓到
 * 1280×900 的 y=984（票 15 critique），現在收成一行、資料夾名搬進搜尋區塊（送單會寫死的就是它）。
 *
 * **觀看區是另一支請求**（`GET /media/{id}/watch`），不擋頁面：身分帶與 Berth 的那一半先畫，Jellyfin 回了才插進
 * 主按鈕與觀看區（首頁兩列的同一個取捨），Jellyfin 慢或連不上時搜尋照樣能用。
 *
 * 票 09（長清單收合）與票 10（缺集一鍵搜）往「季集與入庫」與「檔案與版本」裡填，不重排這一頁。
 */
export function MediaDetailPage({ id }: { id: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const media = useQuery(mediaQueryOptions(id))
  // 季表那兩顆「搜缺的集」按下去時，做事的是搜尋區塊（結果照舊畫在那裡，shape §4、票 10）。
  const search = useRef<SearchHandle>(null)
  const watch = useQuery(watchQueryOptions(id))

  const reload = useMutation({
    mutationFn: () => refresh(id),
    onSuccess: (updated) => queryClient.setQueryData(['media', id], updated),
  })

  if (media.isPending) return <Loading />
  // 後端問不到（不是 TMDB 問不到——那是 200 加一個 `problem`）。
  if (!media.data) return <Offline />

  const found = media.data
  // 一列快照都沒有：整頁只剩下那句理由。有快照時它降級成一條「這是舊的」。
  const blank = found.problem !== null && found.fetched_at === null
  const area = watch.data ?? null
  const refusal = accessRefusal(watch.error)

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-8 px-6 py-8">
      {blank ? (
        <section className="grid gap-4">
          <h1 className="value text-lg font-semibold text-ink">{found.id}</h1>
          <TmdbNotice
            problem={found.problem!}
            detail={found.detail}
            onRetry={() => void media.refetch()}
          />
          <Link to="/" className={GHOST_LINK}>
            {t('media.backToDiscover')}
          </Link>
        </section>
      ) : (
        <>
          <IdentityBand
            media={found}
            carryOn={area && <CarryOn mediaId={id} area={area} />}
            freshness={
              <Freshness
                media={found}
                pending={reload.isPending}
                onRefresh={() => reload.mutate()}
              />
            }
          />

          {area?.kind === 'tv' && <WatchSection mediaId={id} area={area} />}
          {refusal?.reason === 'jellyfin_unreachable' && (
            <WatchDown detail={refusal.detail} onRetry={() => void watch.refetch()} />
          )}

          <SearchPanel media={found} ref={search} />

          {/* `user` 碰到停在待審核的下載只能等（brief §11、M2 票 06）。季表上那幾集是「卡住」，
              這一句說它卡在誰手上。admin 不畫：審核是他自己的事。 */}
          {found.awaiting_review > 0 && <AwaitingReview count={found.awaiting_review} />}

          {/* Berth 的季表：TMDB 的季集與入庫狀態。票 10 的缺集一鍵搜往它的工具列與展開區裡填
              （單季的入口在那一季展開區的第一行，shape §4）。

              `key`：`/media/$mediaId` 是同一條路由，所以在作品之間換頁時這棵樹不重掛，而工具列的
              「只看缺集」是**這一部作品當下的視角**——少了它，上一部篩過的狀態會跟著下一部走
              （目標已在快取裡、沒有讀取中的空檔時特別明顯，票 09b）。 */}
          <SeasonsPanel
            key={found.id}
            media={found}
            watched={area?.kind === 'tv'}
            onSearchMissing={(season) => search.current?.searchMissing(season)}
          />

          <FilesPanel media={found} />
        </>
      )}

      <TmdbAttribution />
    </div>
  )
}

/** 身分帶那一格海報的寬：與 `IdentityBand` 的兩欄（`7rem` / `sm:11rem`）同一份。 */
const DETAIL_POSTER_SIZES = '(min-width: 640px) 11rem, 7rem'

/**
 * 提單抬頭：海報、三個標題、一行識別值、主按鈕、簡介、快照新鮮度。
 *
 * 三個標題都在：顯示用標題是 `h1`，**英文標題是檔名用的那一個**（brief §7.5），原文標題是字幕組會寫在檔名裡的
 * 那一個。顯示用標題與簡介跟著 UI 語言走；EN 介面上 `h1` 就是英文標題，所以不再印第二次。
 *
 * **主按鈕在簡介之前**：簡介再長，它都在第一屏（shape §3）。窄版海報與標題並排，主按鈕、簡介、新鮮度改成整寬
 * ——擠在海報旁那一條窄欄裡的簡介，曾把搜尋推到 390px 的第三屏。
 */
function IdentityBand({
  media,
  carryOn,
  freshness,
}: {
  media: Media
  carryOn: ReactNode
  freshness: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const title = displayRound(i18n.language, { 'zh-Hant': media.title, en: media.title_en })
  const overview = displayRound(i18n.language, { 'zh-Hant': media.overview, en: media.overview_en })
  const poster = displayRound(i18n.language, {
    'zh-Hant': media.poster_url,
    en: media.poster_url_en,
  })

  return (
    <section className="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-5 border-b-2 border-rule-strong pb-8 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-x-6">
      <ArtSlot
        url={poster}
        shape="poster"
        sizes={DETAIL_POSTER_SIZES}
        className="shrink-0 border-2 border-rule sm:row-span-2"
      />
      <div className="grid content-start gap-2">
        {/* 中性色塊：「Berth 為它做過事」是一個事實，不是四個信號色裡的任何一個狀態
            （The Role Is Not A State Rule）。推導出來的，不是一顆按鈕（票 04b）。 */}
        {media.tracked && (
          <p>
            <span className="label bg-deck px-2 py-1.5 text-ink">{t('media.tracked')}</span>
          </p>
        )}
        <h1 className="text-xl leading-snug font-semibold text-ink">{title}</h1>
        {media.title_en !== title && <p className="value text-sm text-ink-dim">{media.title_en}</p>}
        {media.title_original !== media.title_en && media.title_original !== title && (
          <p className="value text-sm text-ink-dim">{media.title_original}</p>
        )}
        <Facts media={media} />
      </div>
      <div className="col-span-2 grid content-start gap-5 sm:col-span-1 sm:col-start-2">
        {carryOn}
        {overview && <p className="max-w-prose text-sm leading-relaxed text-ink-dim">{overview}</p>}
        {freshness}
      </div>
    </section>
  )
}

/**
 * 一行識別值：類型代號、首播 / 上映、季集數（電影是片長）、TMDB id（M1.5 票 08：原本的五列剖面）。
 * `TV` / `MOVIE` 與數字是機器字串，走 `.value`（The Machine String Rule）。
 *
 * **Specials 不算進季數與集數**：TMDB 自己報的 `number_of_seasons` 也不算它，而「4 季 53 集」與封面上印的
 * 「3 季 50 集」對不起來只會讓人以為 Berth 抓錯了。季表本身仍然列出 S00。
 */
function Facts({ media }: { media: Media }) {
  const { t } = useTranslation()
  const seasons = media.seasons.filter((season) => season.season_number > 0)
  // 標籤說的是「首播 / 上映」，所以值就要是那個日期。TMDB 未定檔時只有年份、連年份都沒有時是 `—`。
  const date = media.first_air_date ?? media.year ?? '—'
  // 片長未知時不印：這一行沒有欄名，一個孤零零的 `—` 說不出它是什麼。
  const size =
    media.kind === 'movie'
      ? media.runtime === null
        ? []
        : [t('media.minutes', { count: media.runtime })]
      : [
          t('media.season.count', { count: seasons.length }),
          t('media.episode.count', {
            count: seasons.reduce((total, row) => total + row.episode_count, 0),
          }),
        ]
  const facts = [
    KIND_CODE[media.kind],
    media.kind === 'movie' ? t('media.released', { date }) : t('media.aired', { date }),
    ...size,
    t('media.tmdbId', { id: media.tmdb_id }),
  ]

  return (
    <p className="value flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-ink-dim">
      {facts.map((fact, index) => (
        <span key={index} className="contents">
          {index > 0 && <Dot />}
          <span>{fact}</span>
        </span>
      ))}
    </p>
  )
}

/**
 * 這份快照幾歲了，以及「立刻重抓」。
 *
 * 平常它只是一行小字——快照 24 小時自動刷新（plan §8.3），沒有人需要按這顆按鈕。
 * 它存在是為了 TMDB 剛改過資料的那一刻，以及**快照過期而 TMDB 連不上**的那一刻：
 * 那時整頁仍然畫得出來（存下來的季集是真的），只是要說清楚它是舊的。
 */
function Freshness({
  media,
  pending,
  onRefresh,
}: {
  media: Media
  pending: boolean
  onRefresh: () => void
}) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3">
      {media.problem !== null && (
        <>
          {/* `assigned` 而不是 `blocked`：紅色只代表「在你動手之前走不下去」，而這一格的
              前提正是**頁面照樣畫得出來**，存下來的季集是真的（The One Meaning Rule）。
              順帶把 `role="alert"` 也讓掉——舊快照不該打斷螢幕閱讀器。 */}
          <Notice signal="assigned" label={t('media.stale')}>
            {t(`tmdb.problem.${media.problem}`)}
          </Notice>
          {media.detail && (
            <p className="value text-xs wrap-anywhere text-ink-dim">{media.detail}</p>
          )}
        </>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="text-xs text-ink-dim">
          {t('media.fetchedAt')} <Timestamp at={media.fetched_at} />
        </p>
        <GhostButton type="button" busy={pending} onClick={onRefresh}>
          {pending ? t('media.refreshing') : t('media.refresh')}
        </GhostButton>
      </div>
    </div>
  )
}

/** 讀取中：海報位留一個空位、識別欄位留兩條線。**不會動**——這個世界沒有骨架屏動畫。 */
function Loading() {
  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-8 px-6 py-8" aria-hidden="true">
      <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
        <div className="aspect-[2/3] border-2 border-rule bg-hull" />
        <div className="grid content-start gap-3 pt-1">
          <span className="block h-4 w-3/5 bg-deck" />
          <span className="block h-3 w-2/5 bg-deck" />
        </div>
      </div>
    </div>
  )
}

function Offline() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <p className="max-w-prose text-sm text-ink-dim">{t('discover.off')}</p>
    </div>
  )
}

/**
 * 「等管理員審核」那一句。**中性，不塗信號色**：`assigned` 的意思是「現在需要你」，而看這一頁的
 * `user` 什麼都做不了（The One Meaning Rule）。狀態仍然不只靠顏色——前面是「待審核」的模板字。
 */
function AwaitingReview({ count }: { count: number }) {
  const { t } = useTranslation()
  // 角色在這裡問而不是頁面頂層：沒有停下來的下載時這一塊根本不掛，整頁不必多等一個查詢。
  const me = useQuery(meQueryOptions)
  if (!me.data || me.data.role === 'admin') return null
  return (
    <p className="flex flex-wrap items-start gap-x-3 gap-y-2 border-2 border-rule bg-well px-3 py-2.5">
      <span className="label bg-deck px-2 py-1.5 text-ink">{t('jobs.state.review')}</span>
      <span className="min-w-0 flex-1 self-center text-sm text-ink">
        {t('media.awaitingReview', { count })}
      </span>
    </p>
  )
}

import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { mediaQueryOptions, refresh, type Media } from '../api/media'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { GHOST_LINK, GhostButton, Notice } from '../components/controls'
import { KIND_CODE } from '../components/kind'
import { Timestamp } from '../components/Timestamp'
import { TmdbNotice } from '../components/TmdbNotice'
import { Poster } from '../media/Poster'
import { SeasonList } from '../media/SeasonList'
import { TrackAction } from '../media/TrackAction'
import tmdbLogo from '../assets/tmdb.svg'

/**
 * Media 詳情頁 `/media/:id`（票 04、`.scratch/m1/media-detail-shape.md`）。
 *
 * 這一頁是**決策中心**（brief §13）：使用者剛在探索牆上認出一部作品，來這裡決定
 * 「這是不是我要的那部、要不要交給 Berth 管、入庫到哪裡」。
 *
 * 版面是一張貨櫃提單——上方身分帶（海報 + 識別欄位 + 那一行要簽的動作），下方整寬堆疊。
 * **後兩票往中間插，不重排前面**：票 08 的搜尋結果表插在季集之後，票 13 的檔案與版本清單
 * 再插在它之後（shape brief §3 的區塊序列）。整寬是為了它們——五欄的結果表在一個
 * 5:7 的右欄裡讀不完。
 */
export function MediaDetailPage({ id }: { id: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const media = useQuery(mediaQueryOptions(id))

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
            freshness={
              <Freshness media={found} pending={reload.isPending} onRefresh={() => reload.mutate()} />
            }
          />

          <section className="grid gap-3">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
              <h2 className="label text-ink">{t('media.seasons')}</h2>
              {found.seasons.length > 0 && (
                <p className="value text-xs text-ink-dim">{found.seasons.length}</p>
              )}
            </div>
            {found.kind === 'movie' ? (
              // 電影沒有季集區塊（票 04 驗收）。說一句話，不留一塊空白。
              <p className="max-w-prose text-sm text-ink-dim">{t('media.season.film')}</p>
            ) : found.seasons.length > 0 ? (
              <SeasonList seasons={found.seasons} />
            ) : (
              <p className="max-w-prose text-sm text-ink-dim">{t('media.season.none')}</p>
            )}
          </section>

        </>
      )}

      {/* TMDB 的條款要求顯示標誌與這一句（brief §20.3）。它是法定聲明，不是頁尾裝飾。 */}
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t-2 border-rule pt-4">
        <img src={tmdbLogo} alt="TMDB" height={16} className="h-4 w-auto" />
        <p className="max-w-prose text-xs text-ink-dim">{t('discover.attribution')}</p>
      </footer>
    </div>
  )
}

/**
 * 提單抬頭：海報、三個標題、識別欄位、那一行動作、簡介。
 *
 * 三個標題都在：顯示用標題是 `h1`，**英文標題是檔名用的那一個**（brief §7.5），
 * 原文標題是字幕組會寫在檔名裡的那一個——使用者要認得出三者的關係。
 */
function IdentityBand({ media, freshness }: { media: Media; freshness: ReactNode }) {
  const { t } = useTranslation()
  // **Specials 不算進季數與集數**：TMDB 自己報的 `number_of_seasons` 也不算它，
  // 而「4 季 53 集」與封面上印的「3 季 50 集」對不起來只會讓人以為 Berth 抓錯了。
  // 季集清單本身仍然列出 S00——那一季是真的存在，只是不進總數。
  const seasons = media.seasons.filter((season) => season.season_number > 0)

  return (
    <section className="grid gap-6 border-b-2 border-rule-strong pb-8">
      <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
        <Poster url={media.poster_url} />
        <div className="grid content-start gap-4">
          <div className="grid gap-1">
            <h1 className="text-xl leading-snug font-semibold text-ink">{media.title}</h1>
            {media.title_en !== media.title && (
              <p className="value text-sm text-ink-dim">{media.title_en}</p>
            )}
            {media.title_original !== media.title_en &&
              media.title_original !== media.title && (
                <p className="value text-sm text-ink-dim">{media.title_original}</p>
              )}
          </div>
          {media.overview && (
            <p className="max-w-prose text-sm leading-relaxed text-ink-dim">{media.overview}</p>
          )}
        </div>
      </div>

      <Cutaway title={t('media.identity')}>
        {/* `TV` / `MOVIE` 與 `tmdbid-…` 是機器字串，走 `.value`（The Machine String Rule）。 */}
        <CutawayRow term={t('media.kind')} value={KIND_CODE[media.kind]} />
        <CutawayRow term="tmdb_id" value={media.tmdb_id} code />
        {/* 標籤說的是「首播 / 上映」，所以值就要是那個日期。TMDB 未定檔時只有年份、
            連年份都沒有時是 `—`——欄位不省略，省略會讓整份剖面的基線錯開。 */}
        <CutawayRow term={t('media.year')} value={media.first_air_date ?? media.year ?? '—'} />
        {media.kind === 'movie' ? (
          <CutawayRow
            term={t('media.runtime')}
            value={media.runtime === null ? '—' : t('media.minutes', { count: media.runtime })}
          />
        ) : (
          <CutawayRow
            term={t('media.counts')}
            value={`${t('media.season.count', { count: seasons.length })} · ${t(
              'media.episode.count',
              { count: seasons.reduce((total, row) => total + row.episode_count, 0) },
            )}`}
          />
        )}
        {/* 這一串字是這一頁的署名事實：追蹤之後它會真的出現在檔案系統上、而且改不掉。
            term 走 `.label` 而不是 `code`——`code` 是給**term 本身就是機器字串**的那種列
            （上面的 `tmdb_id`）。這一列的機器字串在 dd，而 dd 本來就是 `.value`。 */}
        <CutawayRow
          term={t(media.tracked ? 'media.folder' : 'media.folderPreview')}
          value={media.folder_name}
        />
      </Cutaway>

      <TrackAction media={media} />
      {freshness}
    </section>
  )
}

/**
 * 這份快照幾歲了，以及「立刻重抓」。
 *
 * 平常它只是一行小字——快照 24 小時自動刷新（plan §8.3），沒有人需要按這顆按鈕。
 * 它存在是為了 TMDB 剛改過資料的那一刻，以及**快照過期而 TMDB 連不上**的那一刻：
 * 那時整頁仍然畫得出來（存下來的季集是真的），只是要說清楚它是舊的。
 *
 * **它住在身分帶裡而不是自己一個區塊**：shape brief §3 的區塊序列只有五塊，而第三塊是
 * 票 08 的搜尋結果表——在那裡多長一塊出來，後面兩票就得重排這一頁。
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
    <section className="grid gap-3">
      {media.problem !== null && (
        <>
          {/* `assigned` 而不是 `blocked`：紅色只代表「在你動手之前走不下去」，而這一格的
              前提正是**頁面照樣畫得出來**，存下來的季集是真的（The One Meaning Rule）。
              順帶把 `role="alert"` 也讓掉——舊快照不該打斷螢幕閱讀器。 */}
          <Notice signal="assigned" label={t('media.stale')}>
            {t(`tmdb.problem.${media.problem}`)}
          </Notice>
          {media.detail && (
            <p className="value text-xs break-words text-ink-dim">{media.detail}</p>
          )}
        </>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="text-xs text-ink-dim">
          {t('media.fetchedAt')} <Timestamp at={media.fetched_at} />
        </p>
        <GhostButton type="button" onClick={onRefresh}>
          {pending ? t('media.refreshing') : t('media.refresh')}
        </GhostButton>
      </div>
    </section>
  )
}

/** 讀取中：海報位留一個空位、識別欄位留兩條線。**不會動**——這個世界沒有骨架屏動畫。 */
function Loading() {
  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-8 px-6 py-8" aria-hidden="true">
      <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-4 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
        <div className="aspect-[2/3] border-2 border-rule bg-well" />
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
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Episode, Season } from '../api/media'
import { CollapsibleRow } from '../components/CollapsibleRow'
import { COMPACT_BUTTON } from '../components/controls'
import { episodeCode, seasonCode } from '../components/episodes'
import { SIGNAL_FILL } from '../components/signal'
import { missingOf } from './missing'

/**
 * 各季各集（`.scratch/m1/media-detail-shape.md` §6，使用者拍板「每季一個可展開列，預設全收」）。
 *
 * **預設全收**的理由是真實資料：TMDB 把名偵探柯南併成一季 1213 集（brief §20.3），
 * 攤平的話那一頁永遠捲不到底下的搜尋結果表（票 08）與檔案清單（票 13）。每一季是一段 `CollapsibleRow`
 * （M1.5 票 09、`.scratch/m1.5/long-lists-shape.md`）：收起的季不渲染集列，展開的季摘要列黏頂、底端也收得起來。
 *
 * 「只看缺集」的開關、整部作品的計數與整部作品的一鍵搜在 `SeasonsPanel`（shape §4 的工具列）；
 * 這一份只收它的結果，另外在每一季的展開區第一行放那一季的一鍵搜（票 10）。
 */
export function SeasonList({
  seasons,
  missingOnly,
  onSearchMissing,
}: {
  seasons: readonly Season[]
  missingOnly: boolean
  /** 這一季缺的集一鍵搜（M1.5 票 10）。 */
  onSearchMissing: (season: number) => void
}) {
  const { t } = useTranslation()
  // 有 Absolute group 的作品才畫絕對編號那一欄——六成的動漫才有（brief §20.3），
  // 沒有的時候整欄不畫，而不是留一整排 `—`。
  const absolute = seasons.some((season) =>
    season.episodes.some((episode) => episode.absolute_number !== null),
  )

  return (
    <div className="grid gap-px bg-rule">
      {seasons.map((season) => {
        const gaps = missingOf(season)
        return (
          <CollapsibleRow
            key={season.season_number}
            name={seasonCode(season.season_number)}
            summary={<SeasonSummary season={season} gaps={missingOnly ? gaps.length : null} />}
          >
            {() => (
              <>
                {/* 這一季缺的集一鍵搜（票 10）：在展開區的**第一行**，不在 `<summary>` 裡
                    （The Summary Is One Button Rule）。沒有缺集的季不畫這一行。 */}
                {gaps.length > 0 && (
                  <p className="border-b-2 border-rule px-4 py-2">
                    <button
                      type="button"
                      onClick={() => onSearchMissing(season.season_number)}
                      className={COMPACT_BUTTON}
                    >
                      {t('media.season.searchMissingSeason', {
                        season: seasonCode(season.season_number),
                      })}
                    </button>
                  </p>
                )}
                <SeasonBody
                  season={season}
                  episodes={missingOnly ? gaps : season.episodes}
                  missingOnly={missingOnly}
                  absolute={absolute}
                />
              </>
            )}
          </CollapsibleRow>
        )
      })}
    </div>
  )
}

/** `gaps` 是 `null` 時沒開「只看缺集」，不說缺幾集。 */
function SeasonSummary({ season, gaps }: { season: Season; gaps: number | null }) {
  const { t } = useTranslation()

  return (
    <>
      <span className="value text-sm font-semibold text-ink">
        {seasonCode(season.season_number)}
      </span>
      {/* 窄版上季名自己一行：與集數擠在同一行時 `flex-1` 被壓成 0 寬，兩段字疊在一起
          （票 15 在 342px 內容寬量到）。 */}
      <span className="min-w-0 basis-full text-sm break-words text-ink sm:basis-0 sm:flex-1">
        {season.name}
      </span>
      <span className="value text-xs text-ink-dim">
        {t('media.episode.count', { count: season.episode_count })}
      </span>
      {season.aired > 0 && (
        // 兩個數字由後端算（shape brief §7）：分母是播出了的集數，與媒體庫卡片同一個定義。
        <span className="value text-xs text-ink">
          {t('inventory.episodes', { imported: season.imported, aired: season.aired })}
        </span>
      )}
      {gaps !== null &&
        (gaps > 0 ? (
          <span className="value text-xs text-ink">
            {t('media.season.missing', { count: gaps })}
          </span>
        ) : (
          <span className="value text-xs text-ink-dim">{t('media.season.noneMissing')}</span>
        ))}
      <span className="value w-24 text-right text-xs text-ink-dim">{season.air_date ?? '—'}</span>
    </>
  )
}

function SeasonBody({
  season,
  episodes,
  missingOnly,
  absolute,
}: {
  season: Season
  episodes: readonly Episode[]
  missingOnly: boolean
  absolute: boolean
}) {
  const { t } = useTranslation()

  if (season.episodes.length === 0) {
    return <p className="px-4 py-3 text-xs text-ink-dim">{t('media.season.empty')}</p>
  }
  if (episodes.length === 0 && missingOnly) {
    return <p className="px-4 py-3 text-xs text-ink-dim">{t('media.season.noneMissingHere')}</p>
  }
  return (
    // 集表過寬時由**它自己**橫向捲動，不是整頁（shape brief §7）。
    // 欄序是**集號 → 絕對編號 → 入庫 → 集名**：絕對編號貼著集號（shape §8），而「入庫」
    // 是這張表在這一頁存在的理由——它原本排在最後，390px 上整欄在捲動範圍外（票 15）。
    // 片長與播出日窄版不畫，表就不必比畫面寬。
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left sm:min-w-[36rem]">
        <thead>
          <tr className="border-b-2 border-rule">
            <th scope="col" className="label px-4 py-2 whitespace-nowrap text-ink-dim">
              {t('media.episode.number')}
            </th>
            {absolute && (
              <th scope="col" className="label px-4 py-2 text-right whitespace-nowrap text-ink-dim">
                {t('media.episode.absolute')}
              </th>
            )}
            <th scope="col" className="label px-4 py-2 whitespace-nowrap text-ink-dim">
              {t('media.episode.inLibrary')}
            </th>
            <th scope="col" className="label px-4 py-2 whitespace-nowrap text-ink-dim">
              {t('media.episode.name')}
            </th>
            <th
              scope="col"
              className="label hidden px-4 py-2 text-right text-ink-dim sm:table-cell"
            >
              {t('media.episode.runtime')}
            </th>
            <th
              scope="col"
              className="label hidden px-4 py-2 text-right text-ink-dim sm:table-cell"
            >
              {t('media.episode.airDate')}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {episodes.map((episode) => (
            <EpisodeRow key={episode.episode_number} episode={episode} absolute={absolute} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EpisodeRow({ episode, absolute }: { episode: Episode; absolute: boolean }) {
  const { t } = useTranslation()

  return (
    <tr>
      <td className="value px-4 py-2 text-xs text-ink-dim">
        {episodeCode(episode.episode_number)}
      </td>
      {absolute && (
        <td className="value px-4 py-2 text-right text-xs text-ink-dim">
          {/* 沒有排進 group 的特輯就是沒有絕對編號。`—` 而不是省略——欄位消失會讓基線錯開。 */}
          {episode.absolute_number === null ? '—' : `#${episode.absolute_number}`}
        </td>
      )}
      {/* `whitespace-nowrap`：窄版上集名那一欄會吃掉寬度，狀態被擠成一字一行（票 15 實跑）。 */}
      <td className="px-4 py-2 whitespace-nowrap">
        <EpisodeState status={episode.status} />
      </td>
      <td className="px-4 py-2 text-sm break-words text-ink">{episode.name}</td>
      <td className="value hidden px-4 py-2 text-right text-xs text-ink-dim sm:table-cell">
        {episode.runtime === null ? '—' : t('media.minutesShort', { count: episode.runtime })}
      </td>
      <td className="value hidden px-4 py-2 text-right text-xs text-ink-dim sm:table-cell">
        {episode.air_date ?? '—'}
      </td>
    </tr>
  )
}

/**
 * 一集在媒體庫裡的樣子（票 13）。
 *
 * **常態不塗漆，例外才塗**：一季 1213 集的表不該是一整欄綠色勾勾（DESIGN.md 拒絕的那一種）。
 * 下載中是 `working`；卡住是 `assigned`——它要人去下載列表看是哪一筆停下來了，所以它是一條連結。
 */
function EpisodeState({ status }: { status: Episode['status'] }) {
  const { t } = useTranslation()
  const label = t(`media.episode.state.${status}`)

  if (status === 'stuck') {
    return (
      <Link
        to="/jobs"
        className={`label inline-flex min-h-6 items-center px-1.5 ${SIGNAL_FILL.assigned}`}
      >
        {label}
      </Link>
    )
  }
  if (status === 'downloading') {
    return <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.working}`}>{label}</span>
  }
  return (
    <span className={`label ${status === 'unaired' ? 'text-ink-dim' : 'text-ink'}`}>{label}</span>
  )
}

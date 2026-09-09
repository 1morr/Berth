import { useTranslation } from 'react-i18next'

import type { Episode, Season } from '../api/media'

/**
 * 各季各集（`.scratch/m1/media-detail-shape.md` §6，使用者拍板「每季一個可展開列，預設全收」）。
 *
 * 用原生 `<details>`：這個系統沒有 dropdown / accordion 元件，而原生的鍵盤與螢幕閱讀器行為
 * 比重寫一份好（DESIGN.md 的元件基礎）。`<summary>` 已經在全域 `:focus-visible` 的選擇器裡
 * ——那是票 11 補進去的，少了它 Chrome 會退回 0.67px 的預設焦點環。
 *
 * **預設全收**的理由是真實資料：TMDB 把名偵探柯南併成一季 1213 集（brief §20.3），
 * 攤平的話那一頁永遠捲不到底下的搜尋結果表（票 08）與檔案清單（票 13）。
 */
export function SeasonList({ seasons }: { seasons: readonly Season[] }) {
  const { t } = useTranslation()
  // 有 Absolute group 的作品才畫絕對編號那一欄——六成的動漫才有（brief §20.3），
  // 沒有的時候整欄不畫，而不是留一整排 `—`。
  const absolute = seasons.some((season) =>
    season.episodes.some((episode) => episode.absolute_number !== null),
  )

  return (
    <div className="grid gap-px bg-rule">
      {seasons.map((season) => (
        // `min-w-0`：grid 項目的 `min-width` 預設是 `auto`，所以它不肯縮到比內容窄——少了
        // 這一條，展開的集表會把**整頁**撐寬並橫向捲動（390px 實跑量到 560px），
        // 而該捲的是集表自己那一格（shape brief §7）。
        <details key={season.season_number} className="group min-w-0 bg-well">
          <summary className="flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 marker:content-none">
            <span className="value text-sm font-semibold text-ink">
              {seasonCode(season.season_number)}
            </span>
            <span className="min-w-0 flex-1 text-sm text-ink">{season.name}</span>
            <span className="value text-xs text-ink-dim">
              {t('media.episode.count', { count: season.episode_count })}
            </span>
            <span className="value w-24 text-right text-xs text-ink-dim">
              {season.air_date ?? '—'}
            </span>
          </summary>

          {season.episodes.length > 0 ? (
            // 集表過寬時由**它自己**橫向捲動，不是整頁（shape brief §7）。
            <div className="overflow-x-auto border-t-2 border-rule bg-hull">
              <table className="w-full min-w-[32rem] border-collapse text-left">
                <thead>
                  <tr className="border-b-2 border-rule">
                    <th scope="col" className="label px-4 py-2 text-ink-dim">
                      {t('media.episode.number')}
                    </th>
                    <th scope="col" className="label px-4 py-2 text-ink-dim">
                      {t('media.episode.name')}
                    </th>
                    {absolute && (
                      <th scope="col" className="label px-4 py-2 text-right text-ink-dim">
                        {t('media.episode.absolute')}
                      </th>
                    )}
                    <th scope="col" className="label px-4 py-2 text-right text-ink-dim">
                      {t('media.episode.runtime')}
                    </th>
                    <th scope="col" className="label px-4 py-2 text-right text-ink-dim">
                      {t('media.episode.airDate')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {season.episodes.map((episode) => (
                    <EpisodeRow
                      key={episode.episode_number}
                      episode={episode}
                      absolute={absolute}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="border-t-2 border-rule bg-hull px-4 py-3 text-xs text-ink-dim">
              {t('media.season.empty')}
            </p>
          )}
        </details>
      ))}
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
      <td className="px-4 py-2 text-sm text-ink">{episode.name}</td>
      {absolute && (
        <td className="value px-4 py-2 text-right text-xs text-ink-dim">
          {/* 沒有排進 group 的特輯就是沒有絕對編號。`—` 而不是省略——欄位消失會讓基線錯開。 */}
          {episode.absolute_number === null ? '—' : `#${episode.absolute_number}`}
        </td>
      )}
      <td className="value px-4 py-2 text-right text-xs text-ink-dim">
        {episode.runtime === null ? '—' : t('media.minutesShort', { count: episode.runtime })}
      </td>
      <td className="value px-4 py-2 text-right text-xs text-ink-dim">{episode.air_date ?? '—'}</td>
    </tr>
  )
}

/**
 * `S01` / `E01`：與 `BTH 1` 同一個語域的分類代號，在哪個語言都是同一串字母數字，
 * 所以不走 i18n，也不走 `.label`（它會把拉丁字母大寫掉，而這兩個本來就是大寫）。
 */
function seasonCode(season: number) {
  return `S${String(season).padStart(2, '0')}`
}

function episodeCode(episode: number) {
  return `E${String(episode).padStart(2, '0')}`
}

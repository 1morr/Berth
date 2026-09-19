import type { Episode, Season } from '../api/media'

/**
 * 這一季缺的那幾集（M1.5 票 09）。
 *
 * **缺＝`missing`**：已經播出、而且沒有任何下載在處理它。卡住、下載中、未播出都不算（使用者拍板）——
 * 前兩者已經有東西在處理，第三者還沒播。判定在後端，這裡只挑出來。
 *
 * 工具列要數整部作品缺幾集、季表要列出是哪幾集，兩邊用同一份：同一個判準各寫一份遲早會分岔。
 */
export function missingOf(season: Season): Episode[] {
  return season.episodes.filter((episode) => episode.status === 'missing')
}

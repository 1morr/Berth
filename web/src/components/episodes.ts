import type { PlanItem } from '../api/plans'

/**
 * 季集代號：`S01`、`E01`、`S01E01-E02`。
 *
 * **不走 i18n**：它們與 `BTH 1` 同一個語域，也與檔名裡的那一段是同一個東西——翻譯它們等於讓
 * 畫面上的季集與磁碟上的檔名對不起來（The Machine String Rule）。也不走 `.label`，那會把拉丁
 * 字母大寫掉，而這幾個本來就是大寫。
 *
 * 季集表、計劃、帳本與版本群組用同一份（票 11、13）：同一個代號各寫一份遲早會分岔。
 */

export function seasonCode(season: number): string {
  return `S${pad(season)}`
}

export function episodeCode(episode: number): string {
  return `E${pad(episode)}`
}

/**
 * `S01E01` / `S01E01-E02`（Jellyfin 認得的寫法，brief §6.6）。電影沒有季集，回空字串。
 *
 * 只要那三格：計劃的一列、帳本的一筆與版本的一組都用它們說自己蓋到哪幾集。
 */
export function formatEpisode(
  item: Pick<PlanItem, 'season' | 'episode_start' | 'episode_end'>,
): string {
  if (item.season === null || item.episode_start === null) return ''
  const end =
    item.episode_end && item.episode_end !== item.episode_start
      ? `-${episodeCode(item.episode_end)}`
      : ''
  return `${seasonCode(item.season)}${episodeCode(item.episode_start)}${end}`
}

/**
 * Jellyfin 那一端的集（繼續觀看與下一集的橫卡、Media 詳情的選季選集）：`formatEpisode` 的寫法，但 Jellyfin
 * 認不出編號時只剩有的那一段（`S01`、`E05`），兩個都沒有是空字串。
 */
export function formatJellyfinEpisode(
  item: Pick<PlanItem, 'season' | 'episode_start' | 'episode_end'>,
): string {
  if (item.season !== null && item.episode_start !== null) return formatEpisode(item)
  if (item.season !== null) return seasonCode(item.season)
  if (item.episode_start !== null) return episodeCode(item.episode_start)
  return ''
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

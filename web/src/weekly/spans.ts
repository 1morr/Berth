import { episodeCode, seasonCode } from '../components/episodes'

/**
 * `S01E01–E03, E05, S02E01`：同一季接著寫集，換季才再寫季（與通知同一個寫法，
 * `berth/services/notify.py` 的 `describe_spans`）。`spans` 是 `[季, 起, 迄]`，後端已經排好、併好。
 */
export function describeSpans(spans: readonly (readonly [number, number, number])[]): string {
  const parts: string[] = []
  let seasonNow: number | null = null
  for (const [season, start, end] of spans) {
    const episodes =
      start === end ? episodeCode(start) : `${episodeCode(start)}–${episodeCode(end)}`
    parts.push(season === seasonNow ? episodes : `${seasonCode(season)}${episodes}`)
    seasonNow = season
  }
  return parts.join(', ')
}

/** 這些段共蓋到幾集。 */
export function countEpisodes(spans: readonly (readonly [number, number, number])[]): number {
  return spans.reduce((sum, [, start, end]) => sum + (end - start + 1), 0)
}

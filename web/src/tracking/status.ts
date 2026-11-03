import type { TFunction } from 'i18next'

import type { LateEpisode, TrackedWork } from '../api/keepingUp'
import { formatCoverage } from '../components/episodes'

/**
 * 狀態那一格的字（M5.5 票 12，`.scratch/m5.5/tracking-shape.md`）。結論是後端算好的（`domain.WhyNot`），
 * 這裡只決定怎麼念：**下載停滯要說出來**——`WhyNot` 把它併進「下載中」，結論是下載中而有一集停滯時就只說
 * 「下載停滯」；結論是別的（更要人看的）時兩個都說。沒有 TMDB 快照時沒有結論。
 */
export function statusWords(t: TFunction, work: TrackedWork): string[] {
  const words: string[] = []
  if (work.conclusion && !(work.stalled && work.conclusion === 'downloading'))
    words.push(t(`tracking.conclusion.${work.conclusion}`))
  if (work.stalled) words.push(t('tracking.stalled'))
  return words
}

/** 晚的集寫成 `S01 E05–E06`（`formatCoverage`）；跨季時一季一段。 */
export function lateSpans(late: readonly LateEpisode[]): string {
  const seasons = [...new Set(late.map((one) => one.season))].sort((a, b) => a - b)
  return seasons
    .map((season) =>
      formatCoverage(
        season,
        late
          .filter((one) => one.season === season)
          .map((one) => ({ episode_start: one.episode, episode_end: one.episode })),
      ),
    )
    .join(', ')
}

/** 「看這筆下載」連的那一筆：晚的集裡第一筆卡住的 Job；沒有下載卡住（字幕組沒發）是 `null`。 */
export function stuckJob(late: readonly LateEpisode[]): string | null {
  return late.find((one) => one.jobs.length > 0)?.jobs[0] ?? null
}

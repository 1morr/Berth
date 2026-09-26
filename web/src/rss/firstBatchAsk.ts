import type { TFunction } from 'i18next'

import type { Schemas } from '../api/schemas'
import { episodeCode, seasonCode } from '../components/episodes'

/** 還沒確認的 RSS Series 在問人什麼（M4 票 11，`services.first_batch.asks`）。 */
export type FirstBatchAsk = Schemas['FirstBatchAskOut']

/**
 * 「確認 BLACK TORCH × ANi 的季集對應：S01 E01–E04 由集號直接對應」。審核頁那一組與作品頁的「第一批待確認」
 * 說同一句（M4 票 11）：要人看的是季集怎麼對，而不是有幾個檔案在等。
 *
 * 集數照 `formatCoverage` 的寫法（季代號與集號之間空一格、範圍用 en dash）：`S01E01-E04` 是 Jellyfin 的多集檔，
 * 寫成那樣會被讀成一個檔案。字幕組讀不出來時只說作品。
 */
export function firstBatchAskText(
  t: TFunction,
  { title, group, ask }: { title: string; group: string; ask: FirstBatchAsk },
): string {
  const episodes = ask.spans
    .map(
      ({ season, start, end }) =>
        `${seasonCode(season)} ${episodeCode(start)}${end !== start ? `–${episodeCode(end)}` : ''}`,
    )
    .join(t('rss.firstBatch.separator'))
  const basis = t(`rss.firstBatch.basis.${ask.basis}`)
  return group
    ? t('rss.firstBatch.ask', { title, group, episodes, basis })
    : t('rss.firstBatch.askUngrouped', { title, episodes, basis })
}

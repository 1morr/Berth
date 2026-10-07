import type { IndexerSetup, SiteCheck } from '../api/setup'
import { useRemembered } from './remembered'

/** 一站在畫面上的測試狀態：測試中，或測過的結論。還沒測的不在表上。 */
export type CheckState = 'testing' | SiteCheck

/** 把新的結論疊上去，同一站以新的為準。 */
export function withChecks(
  was: ReadonlyMap<string, CheckState>,
  rows: readonly SiteCheck[],
): ReadonlyMap<string, CheckState> {
  return new Map([...was, ...rows.map((row) => [row.definition_name, row] as const)])
}

/**
 * 這一台 Prowlarr 每一站在畫面上的測試結論。起點是上一次「加入」（或主鍵，M4 票 44）的結論——回頭看時
 * 沒通過的那幾站仍說得出為什麼；之後疊上這一頁按的測試。主鍵（`RecommendedSites`）與「進階」的逐站清單
 * （`AddSites`）共用同一份。
 */
export function useSiteChecks(indexers: IndexerSetup) {
  return useRemembered<ReadonlyMap<string, CheckState>>(
    ['indexer-checks', indexers.base_url],
    () => new Map(indexers.checks.map((row) => [row.definition_name, row])),
  )
}

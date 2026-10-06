import type { IndexerSetup, SetupStatus } from '../api/setup'
import { STEP } from './navigation'
import { connected } from './signals'

/** 連上之後畫哪一種：套件內、既有 Prowlarr。 */
export type IndexerMode = 'bundled' | 'prowlarr'

/** 清單說的來源與選擇不一致（剛選下去、清單還沒重讀回來）時是 `null`：不畫另一種的東西。 */
export function modeOf(indexers: IndexerSetup, chosen: string | undefined): IndexerMode | null {
  if (indexers.origin === null || indexers.origin !== chosen) return null
  // 套件內那一台讀不到清單時也是 `'bundled'`（M4 票 27）：呼叫端只在連線卡綠時問，這時讀不到是 key 被換掉
  // 這類事，畫「讀不到」與「重新讀取」，不把整段收掉。
  if (indexers.origin === 'bundled') return 'bundled'
  return 'prowlarr'
}

/** 頁 4 還差的事，前進鍵的位置照它列（`BerthNav` 的 `missing`）。 */
export type IndexerGap = 'sites' | 'login'

/**
 * 頁 4 還沒做完時差什麼（M4 票 27）：加站之後登入區在兩屏之外，前進鍵不出現也沒說為什麼。
 *
 * 條件照後端的 `_indexer_settled`：Prowlarr（套件內或既有）上至少一站，套件內那一台另外要介面登入
 * 有結論；跳過了就什麼都不差。站數看的是這一次讀到的清單，後端看的是上一次連線測試記的數——兩者
 * 不一致時 `IndexerStep` 自動重新測試一次。連不上、清單讀不到時說不出差什麼，不列。
 */
export function indexerGaps(status: SetupStatus, indexers: IndexerSetup): IndexerGap[] {
  if (status.current_step !== STEP.indexer || indexers.skipped || indexers.error) return []
  const service = status.services.find((row) => row.kind === 'prowlarr')
  const mode = connected(service) ? modeOf(indexers, service?.origin) : null
  if (mode !== 'bundled' && mode !== 'prowlarr') return []
  const gaps: IndexerGap[] = indexers.sites.length === 0 ? ['sites'] : []
  const login = indexers.steps.find((step) => step.step === 'prowlarr_login')
  if (mode === 'bundled' && login?.status !== 'ok' && login?.status !== 'skipped') {
    gaps.push('login')
  }
  return gaps
}

/**
 * 前進鍵位置那一句「還差」的每一件：怎麼說、按了去哪一區（那一區的 `id`）。查表：動態組 key 過不了
 * `strictKeyChecks`。
 */
export const GAP = {
  sites: { label: 'indexer.gap.sites', target: 'add-sites' },
  login: { label: 'indexer.gap.login', target: 'prowlarr-login' },
} as const satisfies Record<IndexerGap, { label: string; target: string }>

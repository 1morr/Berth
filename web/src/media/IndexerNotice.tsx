import { useTranslation } from 'react-i18next'

import type { IndexerProblem } from '../api/search'
import { Notice } from '../components/controls'
import { SettingsHint } from '../components/SettingsHint'
import { Timestamp } from '../components/Timestamp'

/**
 * 索引站那邊沒搜到東西時畫面說什麼（票 08 驗收：可行動的說明，不是空清單）。
 *
 * 與 `TmdbNotice` 同一個道理，每一種理由的**下一步不同**：`not_configured` 是精靈第 6 步跳過了
 * ——那不是失敗，是還沒接，所以它用 `assigned`（需要你）而不是 `blocked`（走不下去）。
 * `budget_exhausted`（M3 票 20）是 Berth 自己先停手、等得到，配 `neutral`（不需要你，也還沒完成）。
 * 其餘三種都是真的問不動，配 `blocked`。
 */
export function IndexerNotice({
  problem,
  detail,
  retryAt = null,
}: {
  problem: IndexerProblem
  detail: string
  retryAt?: string | null
}) {
  const { t } = useTranslation()
  const pending = problem === 'not_configured'
  const waiting = problem === 'budget_exhausted'
  // 位址與憑證都在設定的索引站那一頁改，所以索引站的問題都連得過去；`no_query` 例外——
  // 那是這部作品的 TMDB 快照還沒抓到，與索引站無關，去設定也修不了；預算用完也是，等就好。
  const toSettings = problem !== 'no_query' && !waiting

  return (
    <div className="grid max-w-prose gap-3">
      <Notice
        signal={pending ? 'assigned' : waiting ? 'neutral' : 'blocked'}
        label={t(`search.problem.${problem}.label`)}
      >
        {t(`search.problem.${problem}.body`)}
      </Notice>
      {waiting && retryAt && (
        <p className="text-xs text-ink-dim">
          {t('search.problem.retryAt')} <Timestamp at={retryAt} />
        </p>
      )}
      {detail && <p className="value text-xs wrap-anywhere text-ink-dim">{detail}</p>}
      {toSettings && <SettingsHint slot="prowlarr" fallback={t('search.problem.askAdmin')} />}
    </div>
  )
}

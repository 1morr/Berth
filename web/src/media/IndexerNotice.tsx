import { useTranslation } from 'react-i18next'

import type { IndexerProblem } from '../api/search'
import { berthNumberOf } from '../components/berths'
import { Notice } from '../components/controls'
import { SetupHint } from '../components/SetupHint'

/**
 * 索引站那邊沒搜到東西時畫面說什麼（票 08 驗收：可行動的說明，不是空清單）。
 *
 * 與 `TmdbNotice` 同一個道理，五種理由的**下一步不同**：`not_configured` 是精靈第 6 步跳過了
 * ——那不是失敗，是還沒接，所以它用 `assigned`（需要你）而不是 `blocked`（走不下去）。
 * 其餘四種都是真的問不動，配 `blocked`。
 */
export function IndexerNotice({ problem, detail }: { problem: IndexerProblem; detail: string }) {
  const { t } = useTranslation()
  const pending = problem === 'not_configured'
  // 位址與憑證都在精靈的第 6 步改，所以四種索引站的問題都連得過去；`no_query` 例外——
  // 那是這部作品的 TMDB 快照還沒抓到，與索引站無關，去精靈也修不了。
  const toSetup = problem !== 'no_query'

  return (
    <div className="grid max-w-prose gap-3">
      <Notice
        signal={pending ? 'assigned' : 'blocked'}
        label={t(`search.problem.${problem}.label`)}
      >
        {t(`search.problem.${problem}.body`)}
      </Notice>
      {detail && <p className="value text-xs wrap-anywhere text-ink-dim">{detail}</p>}
      {toSetup && (
        // 「來源」那一格：索引站與 TMDB 兩步都在那裡。
        <SetupHint
          berth={berthNumberOf('prowlarr')}
          label={t('search.problem.toSetup')}
          fallback={t('search.problem.askAdmin')}
        />
      )}
    </div>
  )
}

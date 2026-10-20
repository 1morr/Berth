import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import type { IndexerProblem } from '../api/search'
import { GHOST_LINK, Notice } from '../components/controls'
import { SettingsHint } from '../components/SettingsHint'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { SUBSCRIBE_ANCHOR } from './SubscribePanel'

/**
 * 索引站那邊沒搜到東西時畫面說什麼（票 08 驗收：可行動的說明，不是空清單）。
 *
 * 與 `TmdbNotice` 同一個道理，每一種理由的**下一步不同**：`not_configured` 是沒有接索引站——精靈頁 4
 * 說了之後再說，或管理員在設定選了不用 Prowlarr（M4 票 61）。那是一個選擇，不是失敗，也不需要你：配
 * `neutral`，給兩條路——接 Prowlarr，或用同一頁的 RSS 訂閱。
 * `too_many_queries`（M4 票 84）是開了太多名字與季，要你關掉幾個，配 `assigned`；畫面在按下去之前就停用了
 * 搜尋鍵，它只在直接打 API 時出現。其餘三種都是真的問不動，配 `blocked`；服務回的原文收進技術細節
 * （M4 票 21 的分層：人話在前，原文在後）。
 */
export function IndexerNotice({ problem, detail }: { problem: IndexerProblem; detail: string }) {
  const { t } = useTranslation()
  const unconnected = problem === 'not_configured'
  // 位址與憑證都在設定的索引站那一頁改，所以索引站的問題都連得過去；`no_query` 例外——
  // 那是這部作品的 TMDB 快照還沒抓到，與索引站無關，去設定也修不了；
  // 查詢太多是這一區塊的 chip 開太多，關掉就好。沒有接索引站有自己的兩條路（`Unconnected`）。
  const toSettings = problem !== 'no_query' && problem !== 'too_many_queries' && !unconnected

  return (
    <div className="grid max-w-prose gap-3">
      <Notice
        signal={unconnected ? 'neutral' : problem === 'too_many_queries' ? 'assigned' : 'blocked'}
        label={t(`search.problem.${problem}.label`)}
      >
        {t(`search.problem.${problem}.body`)}
      </Notice>
      {unconnected && <Unconnected />}
      {toSettings && <SettingsHint slot="prowlarr" fallback={t('search.problem.askAdmin')} />}
      <TechnicalDetails lines={[detail]} />
    </div>
  )
}

/**
 * 沒有接索引站時的兩條路：設定 → Prowlarr，或這一頁的 RSS 訂閱（只有 admin 畫得出那一段，
 * `MediaDetailPage`）。一般使用者兩條都走不了，請管理員。
 */
function Unconnected() {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)

  if (me.data?.role !== 'admin') {
    return <p className="text-sm text-ink-dim">{t('search.problem.askAdminUnconnected')}</p>
  }
  return (
    <div className="flex flex-wrap gap-3">
      <SettingsHint slot="prowlarr" fallback={t('search.problem.askAdmin')} />
      <a href={`#${SUBSCRIBE_ANCHOR}`} className={GHOST_LINK}>
        {t('search.problem.toSubscribe')}
      </a>
    </div>
  )
}

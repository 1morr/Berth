import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import type { TmdbProblem } from '../api/schemas'
import { GhostButton, Notice } from './controls'
import { SettingsHint } from './SettingsHint'
import { TechnicalDetails } from './TechnicalDetails'

/**
 * 拿不到 TMDB 時畫面說什麼（票 03 驗收：可行動的錯誤，不是空白畫面）。
 *
 * 四種理由的**下一步不同**，所以不共用一句話：憑證的兩種要人去設定的 TMDB 那一頁，連不上只能重試，
 * `not_found` 連重試都沒有意義。把它們合成「TMDB 錯誤」等於把使用者丟回去自己猜。
 *
 * 探索頁（票 03）與 Media 詳情頁（票 04）共用這一塊：兩頁問的是同一台服務，
 * 而「憑證缺失要連到 TMDB 那一頁、而且只對 admin 連」這條規則各寫一份遲早會走樣。
 *
 * 怎麼申請 key 只對 admin 說：時間表（M5.5 票 09）讓這一塊第一次出現在每個人面前，一般使用者原本先被叫去
 * 自己申請、接著又被叫去找管理員（票 19 的 critique）。服務的原文收進技術細節（The Original Is Evidence Rule）。
 */
export function TmdbNotice({
  problem,
  detail,
  onRetry,
}: {
  problem: TmdbProblem
  detail: string
  onRetry: () => void
}) {
  const { t } = useTranslation()
  const credential = problem === 'credential_missing' || problem === 'credential_rejected'
  const admin = useQuery(meQueryOptions).data?.role === 'admin'

  return (
    <div className="grid max-w-prose gap-3 py-2">
      <Notice signal="blocked" label={t('common.failed')}>
        {problem === 'credential_missing' && admin
          ? t('tmdb.problem.credentialMissingAdmin')
          : t(`tmdb.problem.${problem}`)}
      </Notice>
      {credential ? (
        <SettingsHint slot="tmdb" fallback={t('tmdb.problem.askAdmin')} />
      ) : (
        problem === 'unreachable' && (
          // `justify-self-start`：這一格是 grid，不收住的話次要動作會拉成一條滿版的按鈕，
          // 看起來比它該有的份量重（旁邊那條連到設定頁的連結是同一個尺寸）。
          //
          // `not_found` 不給重試：那個 id 上面就是沒有作品，按一百次也一樣。
          <span className="justify-self-start">
            <GhostButton type="button" onClick={onRetry}>
              {t('tmdb.problem.retry')}
            </GhostButton>
          </span>
        )
      )}
      <TechnicalDetails lines={[detail]} />
    </div>
  )
}

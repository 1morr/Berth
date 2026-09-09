import { useTranslation } from 'react-i18next'

import type { TmdbProblem } from '../api/schemas'
import { GhostButton, Notice } from './controls'
import { berthNumberOf } from './berths'
import { SetupHint } from './SetupHint'

/**
 * 拿不到 TMDB 時畫面說什麼（票 03 驗收：可行動的錯誤，不是空白畫面）。
 *
 * 四種理由的**下一步不同**，所以不共用一句話：憑證的兩種要人去精靈第 6 步，連不上只能重試，
 * `not_found` 連重試都沒有意義。把它們合成「TMDB 錯誤」等於把使用者丟回去自己猜。
 *
 * 探索頁（票 03）與 Media 詳情頁（票 04）共用這一塊：兩頁問的是同一台服務，
 * 而「憑證缺失要連到泊位 3、而且只對 admin 連」這條規則各寫一份遲早會走樣。
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

  return (
    <div className="grid max-w-prose gap-3 py-2">
      <Notice signal="blocked" label={t('common.failed')}>
        {t(`tmdb.problem.${problem}`)}
      </Notice>
      {detail && <p className="value text-xs break-words text-ink-dim">{detail}</p>}
      {credential ? (
        // 泊位 3 是**來源**（索引站 + TMDB 兩步），`BERTHS` 的 slot 沿用 `prowlarr`
        // 只是因為那一格的服務判定來自 Prowlarr；TMDB 的第 6 步也在同一格。
        <SetupHint
          berth={berthNumberOf('prowlarr')}
          label={t('tmdb.problem.toSetup')}
          fallback={t('tmdb.problem.askAdmin')}
        />
      ) : (
        problem === 'unreachable' && (
          // `justify-self-start`：這一格是 grid，不收住的話次要動作會拉成一條滿版的按鈕，
          // 看起來比它該有的份量重（旁邊那條連到精靈的連結是同一個尺寸）。
          //
          // `not_found` 不給重試：那個 id 上面就是沒有作品，按一百次也一樣。
          <span className="justify-self-start">
            <GhostButton type="button" onClick={onRetry}>
              {t('tmdb.problem.retry')}
            </GhostButton>
          </span>
        )
      )}
    </div>
  )
}

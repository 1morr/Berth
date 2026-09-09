import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import type { DiscoverProblem } from '../api/discover'
import { GhostButton, Notice } from '../components/controls'
import { berthNumberOf } from '../components/berths'

/**
 * 拿不到 TMDB 時這一頁說什麼（票 03 驗收：可行動的錯誤，不是空白畫面）。
 *
 * 三種理由的**下一步不同**，所以不共用一句話：憑證的兩種要人去精靈第 6 步，連不上只能重試。
 * 把它們合成「TMDB 錯誤」等於把使用者丟回去自己猜。
 */
export function DiscoverNotice({
  problem,
  detail,
  onRetry,
}: {
  problem: DiscoverProblem
  detail: string
  onRetry: () => void
}) {
  const { t } = useTranslation()
  // 精靈跑完之後只有 admin 進得去（後端同時回 403），所以那條連結也只給 admin——
  // 對一般使用者它是死路，而他要的是「去叫管理員」（票 10 code-review 的同一條）。
  const me = useQuery(meQueryOptions)
  const credential = problem !== 'unreachable'

  return (
    <div className="grid max-w-prose gap-3 py-2">
      <Notice signal="blocked" label={t('common.failed')}>
        {t(`discover.problem.${problem}`)}
      </Notice>
      {detail && <p className="value text-xs break-words text-ink-dim">{detail}</p>}
      {credential ? (
        me.data?.role === 'admin' ? (
          <Link
            to="/setup"
            search={{ berth: berthNumberOf('prowlarr') }}
            className="label justify-self-start border-2 border-rule px-4 py-2.5 text-ink hover:border-rule-strong"
          >
            {t('discover.problem.toSetup')}
          </Link>
        ) : (
          <p className="text-sm text-ink-dim">{t('discover.problem.askAdmin')}</p>
        )
      ) : (
        // `justify-self-start`：這一格是 grid，不收住的話次要動作會拉成一條滿版的按鈕，
        // 看起來比它該有的份量重（旁邊那條連到精靈的連結是同一個尺寸）。
        <span className="justify-self-start">
          <GhostButton type="button" onClick={onRetry}>
            {t('discover.problem.retry')}
          </GhostButton>
        </span>
      )}
    </div>
  )
}

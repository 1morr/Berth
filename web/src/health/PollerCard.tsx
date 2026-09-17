import { useTranslation } from 'react-i18next'

import type { PollerView } from '../api/schemas'
import { CutawayRow } from '../components/Cutaway'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import { shortHash } from '../jobs/jobState'

/**
 * 健康頁的「下載迴圈」區塊（`.scratch/m1/live-jobs-shape.md` §3、票 10）。
 *
 * 它回答的是四項服務檢查回答不了的一件事：**三個服務都綠著，而下載列表整片停住**。
 * `qbit_poller` 連不上 qBittorrent 時沒有任何一項會變紅——健康檢查五分鐘才問一次，
 * 而且它問的是「版本讀得到嗎」，不是「輪詢還在跑嗎」。
 *
 * **不是第五個泊位格**：泊位板永遠四格（The Board Never Scrolls Rule），而迴圈不是一個
 * 「接上了沒」的外部服務。它是一個剖面加一份清單。
 */
export function PollerCard({ poller }: { poller: PollerView }) {
  const { t } = useTranslation()
  const failing = poller.failures > 0

  return (
    <section
      // 失敗時線變重，不是變紅——紅色只代表阻擋，而迴圈落後一輪還不是阻擋（The One Meaning Rule）。
      className={`border-2 bg-well ${failing ? 'border-rule-strong' : 'border-rule'}`}
      aria-labelledby="health-poller"
    >
      <h3 id="health-poller" className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink">
        {t('health.poller.title')}
      </h3>

      <dl className="divide-y divide-rule">
        <CutawayRow
          term={t('health.poller.lastRound')}
          value={
            <>
              <Timestamp at={poller.checked_at} />
              {' · '}
              {t('health.poller.every', { seconds: poller.interval_seconds })}
            </>
          }
        />
        <CutawayRow
          term={t('health.poller.failures')}
          value={
            <span className={failing ? 'text-blocked-ink' : undefined}>{poller.failures}</span>
          }
          muted={!failing}
        />
        {poller.error !== '' && (
          // 服務回的原文，不翻譯（與精靈的纜繩同一個規矩：理由翻譯，原文不翻譯）。
          <CutawayRow
            term={t('health.poller.error')}
            value={<span className="text-blocked-ink">{poller.error}</span>}
          />
        )}
      </dl>

      {poller.unknown_torrents.length > 0 && (
        <div className="border-t-2 border-rule px-4 py-4">
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="label text-ink">{t('health.poller.unknown.title')}</span>
            <span className="value text-xs text-ink-dim">
              {t('health.poller.unknown.count', { count: poller.unknown_torrents.length })}
            </span>
          </p>
          <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('health.poller.unknown.help')}</p>
          <ul className="mt-3 grid gap-2">
            {poller.unknown_torrents.map((row) => (
              <li key={row.hash} className="grid min-w-0 gap-1 border-l-2 border-rule pl-3">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {/* `client_state` 是 qBittorrent 的機器字串：中性色塊的形狀，但**字走
                      `.value`**——`.label` 會把 `stalledDL` 大寫成 `STALLEDDL`，而使用者要拿
                      這一串去 qBittorrent 的介面上對照（The Machine String Rule）。 */}
                  <span className="value bg-deck px-1.5 py-1 text-xs text-ink">{row.state}</span>
                  <span className="value min-w-0 text-xs wrap-anywhere text-ink">{row.name}</span>
                </p>
                <p className="value flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim">
                  <span>{row.category}</span>
                  <Dot />
                  <span title={row.hash}>{shortHash(row.hash)}</span>
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

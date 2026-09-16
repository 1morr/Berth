import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { ServiceHealth } from '../api/health'
import { CopyLine } from '../components/controls'
import { SERVICE_LABEL, detailLabel } from '../components/services'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { STATE_LABEL, STATE_SIGNAL, composeCommands, serviceFix, serviceState } from './signals'

/**
 * 一個服務的診斷區塊。
 *
 * 綠燈時只有一行事實（版本、位址、最後成功時間）；紅燈時**就地**展開服務回的原文與
 * 該做什麼，其餘服務的區塊不動——那是票 10 的驗收，也是精靈那條「失敗就地展開」的
 * 同一個規矩。
 */
export function ServiceCard({ row, actions }: { row: ServiceHealth; actions?: ReactNode }) {
  const { t } = useTranslation()
  const state = serviceState(row)
  const failed = state === 'failed'

  return (
    <section
      className={`min-w-0 border-2 bg-well ${failed ? 'border-rule-strong' : 'border-rule'}`}
      aria-labelledby={`service-${row.kind}`}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b-2 border-rule px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[STATE_SIGNAL[state]]}`}>
          {t(STATE_LABEL[state])}
        </span>
        <h3 id={`service-${row.kind}`} className="value text-sm font-semibold text-ink">
          {t(SERVICE_LABEL[row.kind])}
        </h3>
        {row.detail && (
          <span className="value text-xs text-ink">
            <span className="label text-ink-dim">{t(detailLabel(row.kind))}</span> {row.detail}
          </span>
        )}
        {row.base_url && (
          <span className="value ml-auto min-w-0 truncate text-xs text-ink-dim">
            {row.base_url}
          </span>
        )}
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 py-3 text-xs">
        <dt className="label self-center text-ink-dim">{t('health.lastOk')}</dt>
        <dd className="text-ink">
          <Timestamp at={row.last_ok_at} />
        </dd>
        <dt className="label self-center text-ink-dim">{t('health.lastChecked')}</dt>
        <dd className="text-ink">
          <Timestamp at={row.checked_at} />
          {row.failures > 0 && (
            <span className="ml-3 text-blocked-ink">
              {t('health.failures', { count: row.failures })}
            </span>
          )}
        </dd>
      </dl>

      {failed && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p role="alert" className="value max-w-prose break-words text-xs text-blocked-ink">
            {row.error}
          </p>
          {/* 被封了與帳密不對在原文上分得出來，但**下一步不同**才是重點：改帳密只會再
              失敗五次，把封鎖時間重新算一輪（brief §20.2、PRODUCT 原則 4）。所以這一句
              取代平常那段修正說明，而不是接在它後面。 */}
          {row.banned ? (
            <p className="mt-3 max-w-prose text-xs text-ink">{t('health.fix.banned')}</p>
          ) : row.unsupported ? (
            /* 版本太舊也是同一個道理：下一步是升級而不是「檢查容器活著嗎」，而升級不可逆
               （brief §16.4、§20.9）。 */
            <p className="mt-3 max-w-prose text-xs text-ink">{t('health.fix.unsupported')}</p>
          ) : (
            <Fix row={row} />
          )}
        </div>
      )}

      {state === 'drift' && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p className="max-w-prose text-xs text-ink">
            {t('health.fix.drift', { keys: row.drift.join(', ') })}
          </p>
          <p className="value mt-2 text-xs text-ink-dim">{row.drift.join(' · ')}</p>
        </div>
      )}

      {state === 'unconfigured' && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p className="max-w-prose text-xs text-ink">{t('health.fix.unconfigured')}</p>
        </div>
      )}

      {actions && (
        <div className="flex flex-wrap gap-3 border-t-2 border-rule px-4 py-3">{actions}</div>
      )}
    </section>
  )
}

/** 動態組 i18n key 過不了 `strictKeyChecks`，所以查表（票 06 的決定）。 */
const FIX_LABEL = {
  bundled: 'health.fix.bundled',
  existing: 'health.fix.existing',
  unconfigured: 'health.fix.unconfigured',
} as const

/** 紅燈時該做什麼。套件內給指令，既有給「回精靈改連線」。 */
function Fix({ row }: { row: ServiceHealth }) {
  const { t } = useTranslation()
  const kind = serviceFix(row)

  return (
    <>
      <h4 className="label mt-4 text-ink-dim">{t('health.fix.title')}</h4>
      <p className="mt-2 max-w-prose text-xs text-ink-dim">{t(FIX_LABEL[kind])}</p>
      {kind === 'bundled' && (
        <div className="mt-2 grid grid-cols-1 gap-px">
          {composeCommands(row.kind).map((command) => (
            <CopyLine key={command} command={command} />
          ))}
        </div>
      )}
      {kind !== 'bundled' && (
        <Link
          to="/setup"
          className="label mt-3 inline-block border-2 border-rule px-4 py-2.5 hover:border-rule-strong"
        >
          {t('health.toSetup')}
        </Link>
      )}
    </>
  )
}

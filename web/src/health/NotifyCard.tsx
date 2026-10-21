import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { HealthDetail } from '../api/health'
import { CutawayRow } from '../components/Cutaway'
import { Notice } from '../components/controls'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { Timestamp } from '../components/Timestamp'

const SETTINGS_LINK = 'label border-2 border-rule px-4 py-2.5 hover:border-rule-strong'

/**
 * 健康頁的「通知」區塊（M4 票 128）：Discord bot 私訊送得出去嗎。
 *
 * 形狀照 `PollerCard`。**唯一變紅的是 token 被拒**：整個管道停著、要人動手才會恢復，那是阻擋；
 * Discord 連不上或被限速 Berth 自己會再試，只讓線變重（The One Meaning Rule）。
 * 通知管道不算進 `status`，也不是泊位。
 */
export function NotifyCard({ notify, admin }: { notify: HealthDetail['notify']; admin: boolean }) {
  const { t } = useTranslation()
  const waiting = !notify.token_rejected && notify.resume_at !== null && notify.error !== ''

  const settingsLink = admin && (
    <Link to="/settings/notifications" className={SETTINGS_LINK}>
      {t('health.notify.settingsLink')}
    </Link>
  )

  return (
    <section
      // 出事時整塊框換重線（DESIGN.md〈健康頁的卡片〉），不是變紅：紅色只在 token 被拒的那一則 Notice 上。
      className={`border-2 bg-well ${waiting || notify.token_rejected ? 'border-rule-strong' : 'border-rule'}`}
      aria-labelledby="health-notify"
    >
      <h2 id="health-notify" className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink">
        {t('health.notify.title')}
      </h2>

      {!notify.configured ? (
        <dl className="divide-y divide-rule">
          <CutawayRow
            term={t('health.notify.status')}
            value={
              <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span>{t('health.notify.unconfigured')}</span>
                {settingsLink}
              </span>
            }
            muted
          />
        </dl>
      ) : (
        <>
          {notify.token_rejected && (
            <div className="border-b-2 border-rule px-4 py-4">
              <Notice signal="blocked" label={t('health.notify.rejectedChip')}>
                <span className="grid gap-1">
                  <span>{t('health.notify.rejected')}</span>
                  <span>
                    {t(admin ? 'health.notify.rejectedFix' : 'health.notify.rejectedAskAdmin')}
                  </span>
                </span>
              </Notice>
              {admin && <div className="mt-3">{settingsLink}</div>}
              <TechnicalDetails lines={[notify.error]} />
            </div>
          )}

          <dl className="divide-y divide-rule">
            {waiting && (
              <>
                <CutawayRow
                  term={t('health.notify.error')}
                  value={
                    <>
                      <span>
                        {t(
                          notify.failures > 0
                            ? 'health.notify.unavailable'
                            : 'health.notify.rateLimited',
                        )}
                      </span>
                      <TechnicalDetails lines={[notify.error]} />
                    </>
                  }
                />
                <CutawayRow
                  term={t('health.notify.resumeAt')}
                  value={<Timestamp at={notify.resume_at} />}
                />
                {notify.failures > 0 && (
                  <CutawayRow
                    term={t('health.notify.failures')}
                    value={<span className="text-blocked-ink">{notify.failures}</span>}
                  />
                )}
              </>
            )}
            <CutawayRow
              term={t('health.notify.lastSent')}
              value={<Timestamp at={notify.last_sent_at} past />}
            />
            <CutawayRow
              term={t('health.notify.pending')}
              value={t('health.notify.pendingCount', { count: notify.pending })}
              muted={notify.pending === 0}
            />
          </dl>
          <p className="border-t-2 border-rule px-4 py-3 text-xs text-ink-dim">
            {t('health.notify.giveUp')}
          </p>
        </>
      )}
    </section>
  )
}

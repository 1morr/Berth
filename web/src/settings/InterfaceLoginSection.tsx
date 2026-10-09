import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { InterfaceLogin } from '../api/setup'
import type { SetupStep } from '../api/schemas'
import { GhostButton, Notice } from '../components/controls'
import { failureText } from '../components/failures'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { useInterfaceLogin, type LoginService } from '../setup/interfaceLogin'
import { NewLoginFields } from '../setup/InterfaceLoginFields'
import { SettingsSection } from './SettingsFrame'

/** 「儲存」的結果：登入那一條纜繩，或那個服務根本連不上時的原文（兩頁都回 `error`）。 */
export interface LoginOutcome {
  step?: SetupStep
  error: string
}

/**
 * 設定頁的「介面登入」（M4 票 07）：套件內 qBittorrent / Prowlarr 自己的登入。只換登入——不連帶還原
 * 偏好、不重驗站。既有服務沒有這一區（呼叫端不畫它）。
 *
 * **一般的改帳密表單**（M4 票 78，`.scratch/m4/settings-cleanup-shape.md`）：先說目前的帳號，再三格
 * （帳號預填目前那一個、新密碼、再一次），一顆「儲存」。精靈的「沿用 Jellyfin 帳密」不在這裡：那是頁 1
 * 剛打過密碼才成立的捷徑，設定頁讀起來像「沿用上次的設定」。結果照後端那一條纜繩說：寫進去了是
 * 「舊的那一組不能再用」，寫不進去是原文。
 */
export function InterfaceLoginSection({
  service,
  current,
  saving,
  onSave,
}: {
  service: LoginService
  /** Berth 設下的帳號，空字串是還沒設過（M4 票 07 之前跑完精靈的那一台）。 */
  current: string
  saving: boolean
  /** 請求沒走完（Berth 後端）就 reject。 */
  onSave: (login: InterfaceLogin) => Promise<LoginOutcome>
}) {
  const { t } = useTranslation()
  const form = useInterfaceLogin({ service, current, owner: '', alwaysOpen: true, reuse: false })
  const [result, setOutcome] = useState<SetupStep | 'failed' | null>(null)
  // 送出那一刻的欄位版本：之後改了一格，上一次的結果說的就不是這幾格了（M4 票 21）。
  const [sentAt, setSentAt] = useState<number | null>(null)
  const outcome = sentAt === form.edits ? result : null

  function submit(event: FormEvent) {
    event.preventDefault()
    const login = form.take()
    if (!login) return
    setOutcome(null)
    setSentAt(form.edits)
    onSave(login).then(
      ({ step, error }) => {
        // 連不上那個服務時沒有登入那一條，只有原文：照「沒有寫進去」說，原文貼上。
        setOutcome(step ?? { step: '', status: 'failed', detail: '', error })
        if (step?.status === 'ok' || step?.status === 'skipped') form.reset(login.username ?? '')
      },
      () => setOutcome('failed'),
    )
  }

  return (
    <SettingsSection
      id={`settings-${service}-login`}
      title={t('interfaceLogin.settings.title')}
      lede={current ? undefined : t('interfaceLogin.settings.none')}
    >
      <form noValidate onSubmit={submit} className="grid gap-4 sm:max-w-md">
        {current && (
          <p className="text-sm text-ink">
            {t('interfaceLogin.settings.current')}{' '}
            <span className="value font-semibold">{current}</span>
          </p>
        )}
        <NewLoginFields
          service={service}
          form={form}
          passwordLabel={t('interfaceLogin.settings.newPassword')}
        />
        <div className="grid gap-2">
          <div>
            <GhostButton type="submit" busy={saving}>
              {saving ? t('interfaceLogin.settings.saving') : t('interfaceLogin.settings.save')}
            </GhostButton>
          </div>
          <p className="max-w-prose text-xs text-ink-dim">{t('interfaceLogin.settings.after')}</p>
        </div>
        <div aria-live="polite">
          {outcome === 'failed' ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('interfaceLogin.settings.failed')}
            </Notice>
          ) : outcome?.status === 'failed' ? (
            <div>
              <Notice signal="blocked" label={t('common.failed')}>
                {t('interfaceLogin.settings.refused')}{' '}
                {failureText(t, outcome, service === 'qbittorrent' ? 'qBittorrent' : 'Prowlarr')}
              </Notice>
              <TechnicalDetails lines={[outcome.error]} />
            </div>
          ) : outcome ? (
            <Notice signal="secured" label={t('status.ok')}>
              {t('interfaceLogin.settings.saved', { username: outcome.detail })}
            </Notice>
          ) : null}
        </div>
      </form>
    </SettingsSection>
  )
}

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { InterfaceLogin } from '../api/setup'
import type { SetupStep } from '../api/schemas'

/** 「更新登入」的結果：登入那一條纜繩，或那個服務根本連不上時的原文（兩頁都回 `error`）。 */
export interface LoginOutcome {
  step?: SetupStep
  error: string
}
import { GhostButton, Notice } from '../components/controls'
import { useInterfaceLogin } from '../setup/interfaceLogin'
import { InterfaceLoginFields, type LoginService } from '../setup/InterfaceLoginFields'
import { SettingsSection } from './SettingsFrame'

/**
 * 設定頁的「介面登入」（M4 票 07）：套件內 qBittorrent / Prowlarr 自己的登入，與精靈泊位上的是
 * 同一組欄位。只換登入——不連帶還原偏好、不重驗站。既有服務沒有這一區（呼叫端不畫它）。
 *
 * 改登入就是設一組新的，所以三格都必填；帳號預填目前那一個。結果照後端那一條纜繩說：
 * 寫進去了是「舊的那一組不能再用」，寫不進去是原文。
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
  const form = useInterfaceLogin({ current, suggested: current, alwaysOpen: true })
  const [outcome, setOutcome] = useState<SetupStep | 'failed' | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    const login = form.take()
    if (!login) return
    setOutcome(null)
    onSave(login).then(
      ({ step, error }) => {
        // 連不上那個服務時沒有登入那一條，只有原文：照「沒有寫進去」說，原文貼上。
        setOutcome(step ?? { step: '', status: 'failed', detail: '', error })
        if (step?.status === 'ok' || step?.status === 'skipped') form.reset(login.username)
      },
      () => setOutcome('failed'),
    )
  }

  return (
    <SettingsSection
      id={`settings-${service}-login`}
      title={t('interfaceLogin.settings.title')}
      lede={
        current
          ? t('interfaceLogin.settings.current', { username: current })
          : t('interfaceLogin.settings.none')
      }
    >
      <form noValidate onSubmit={submit} className="grid gap-4 sm:max-w-md">
        <InterfaceLoginFields service={service} form={form} />
        <div>
          <GhostButton type="submit" busy={saving}>
            {saving ? t('interfaceLogin.settings.saving') : t('interfaceLogin.settings.save')}
          </GhostButton>
        </div>
        <div aria-live="polite">
          {outcome === 'failed' ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('interfaceLogin.settings.failed')}
            </Notice>
          ) : outcome?.status === 'failed' ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('interfaceLogin.settings.refused')}
              <span className="value mt-1 block text-xs wrap-anywhere">{outcome.error}</span>
            </Notice>
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

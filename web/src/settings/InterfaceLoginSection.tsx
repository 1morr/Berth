import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  loginRefusalOf,
  setupStatusQueryOptions,
  type InterfaceLogin,
  type InterfaceLoginRefusal,
} from '../api/setup'
import type { SetupStep } from '../api/schemas'

/** 「更新登入」的結果：登入那一條纜繩，或那個服務根本連不上時的原文（兩頁都回 `error`）。 */
export interface LoginOutcome {
  step?: SetupStep
  error: string
}
import { GhostButton, Notice } from '../components/controls'
import { failureText } from '../components/failures'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { useInterfaceLogin } from '../setup/interfaceLogin'
import { InterfaceLoginFields, type LoginService } from '../setup/InterfaceLoginFields'
import { SettingsSection } from './SettingsFrame'

/**
 * 設定頁的「介面登入」（M4 票 07）：套件內 qBittorrent / Prowlarr 自己的登入，與精靈泊位上的是
 * 同一組欄位。只換登入——不連帶還原偏好、不重驗站。既有服務沒有這一區（呼叫端不畫它）。
 *
 * 與精靈同一個勾選「沿用 Jellyfin 帳密」（M4 票 15），預設勾選；取消勾選就是設一組新的，三格都必填、
 * 帳號預填目前那一個。結果照後端那一條纜繩說：寫進去了是「舊的那一組不能再用」，寫不進去是原文。
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
  // 沿用時的帳號是擁有者。它讀回來之前不畫欄位：勾選的預設值跟著它定。
  const owner = useQuery(setupStatusQueryOptions).data?.owner

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
      {owner === undefined ? (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      ) : (
        <LoginForm
          service={service}
          current={current}
          owner={owner}
          saving={saving}
          onSave={onSave}
        />
      )}
    </SettingsSection>
  )
}

function LoginForm({
  service,
  current,
  owner,
  saving,
  onSave,
}: {
  service: LoginService
  current: string
  owner: string
  saving: boolean
  onSave: (login: InterfaceLogin) => Promise<LoginOutcome>
}) {
  const { t } = useTranslation()
  const form = useInterfaceLogin({ current, owner, alwaysOpen: true })
  const [result, setOutcome] = useState<SetupStep | 'failed' | InterfaceLoginRefusal | null>(null)
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
      // 沿用 Jellyfin 帳密而 Jellyfin 那一關沒過：說是哪一種，兩台都沒寫（M4 票 15）。
      (error: unknown) => setOutcome(loginRefusalOf(error) ?? 'failed'),
    )
  }

  return (
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
        ) : outcome && 'reason' in outcome ? (
          <Notice signal="blocked" label={t('common.failed')}>
            {t(`interfaceLogin.refused.${outcome.reason}`, { owner })}
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
  )
}

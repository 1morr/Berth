import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { JellyfinConnectInput, JellyfinSetup } from '../api/setup'
import type { SetupStep } from '../api/schemas'
import {
  STICKY_ACTION,
  CopyLine,
  Field,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'

/**
 * 既有 Jellyfin「加入 Berth 路徑」失敗的那一句（plan §9.5）：原文、最常見的原因（沒有把同一個宿主目錄掛在
 * 同一個容器路徑）與它自己的媒體庫設定頁。精靈頁 3 的 Route 那一邊畫它（M4 票 15 把頁 3 併起來之後，
 * 原本列媒體庫的那一塊在精靈裡已經到不了）。
 */
export function AddPathFailure({ step, baseUrl }: { step: SetupStep; baseUrl: string }) {
  const { t } = useTranslation()

  return (
    <div className="mt-4 grid grid-cols-1 gap-2">
      <Notice signal="blocked" label={t('common.failed')}>
        <span className="value wrap-anywhere">{step.error}</span>
      </Notice>
      <p className="max-w-prose text-xs text-ink-dim">{t('jellyfin.libraries.addFailed')}</p>
      <CopyLine command={`${baseUrl}/web/#/dashboard/libraries`} />
    </div>
  )
}

/**
 * 管理員登入換一把 API key，與這一次換 key 的結果。設定的 Jellyfin 那一頁重用它（票 06i）：
 * 使用者在 Jellyfin 撤掉了 Berth 那一把、或換了一台 Jellyfin，都是重新登入一次。
 */
export function JellyfinSignIn({
  setup,
  connecting,
  failed,
  onConnect,
}: {
  setup: JellyfinSetup
  connecting: boolean
  failed: boolean
  onConnect: (input: JellyfinConnectInput) => void
}) {
  const { t } = useTranslation()
  const apiKeyStep = setup.steps.find((row) => row.step === 'api_key')

  return (
    <>
      <SignInForm
        connecting={connecting}
        failed={failed}
        onConnect={onConnect}
        signedIn={setup.api_key_present}
      />

      {apiKeyStep?.status === 'failed' && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            <span className="value wrap-anywhere">{apiKeyStep.error}</span>
          </Notice>
        </div>
      )}
    </>
  )
}

function SignInForm({
  connecting,
  failed,
  signedIn,
  onConnect,
}: {
  connecting: boolean
  failed: boolean
  signedIn: boolean
  onConnect: (input: JellyfinConnectInput) => void
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [blank, setBlank] = useState(false)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!username.trim() || !password) {
      setBlank(true)
      return
    }
    setBlank(false)
    onConnect({ username: username.trim(), password })
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 grid max-w-md gap-4">
      <Field
        label={t('jellyfin.existing.username')}
        value={username}
        autoComplete="off"
        error={blank && !username.trim() ? t('owner.error.blank') : undefined}
        onChange={(event) => setUsername(event.target.value)}
      />
      <PasswordField
        label={t('jellyfin.existing.password')}
        value={password}
        autoComplete="off"
        hint={t('jellyfin.existing.passwordHint')}
        error={blank && !password ? t('owner.error.blank') : undefined}
        onChange={(event) => setPassword(event.target.value)}
      />
      {failed && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('jellyfin.existing.requestFailed')}
        </Notice>
      )}
      <div className={STICKY_ACTION}>
        <PrimaryButton type="submit" busy={connecting}>
          {connecting
            ? t('jellyfin.existing.signingIn')
            : t(signedIn ? 'jellyfin.existing.signInAgain' : 'jellyfin.existing.signIn')}
        </PrimaryButton>
      </div>
    </form>
  )
}

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { BerthPath, BerthPathFailure, JellyfinConnectInput, JellyfinSetup } from '../api/setup'
import {
  STICKY_ACTION,
  CopyLine,
  Field,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { mountSnippet } from '../components/routeChecks'

/** 加不上的原因 → 那一句。查表而不是動態組 key——動態組過不了 `strictKeyChecks`（票 06）。 */
const PATH_FAILED = {
  jellyfin_cannot_see: 'jellyfin.libraries.pathFailed.jellyfin_cannot_see',
  directory: 'jellyfin.libraries.pathFailed.directory',
  jellyfin: 'jellyfin.libraries.pathFailed.jellyfin',
  library_missing: 'jellyfin.libraries.pathFailed.library_missing',
} as const satisfies Record<BerthPathFailure, string>

/**
 * 既有 Jellyfin「加入 Berth 路徑」沒加上的那幾個媒體庫，**一個一條**（M4 票 19，plan §9.5）。
 *
 * Jellyfin 自己只回 404，原因由 Berth 分辨（`reason`）：看不到的那一種說出「它沒掛哪個目錄」並附
 * 它那一份 compose 要加的掛載——不再叫人去 Jellyfin 手動加（那樣同樣會失敗），也不給 Jellyfin 的
 * 網址：Berth 存的是它自己連得到的位址（常常是 `host.docker.internal`），瀏覽器開不了。
 */
export function AddPathFailures({ results, root }: { results: BerthPath[]; root: string }) {
  const { t } = useTranslation()
  const failed = results.filter((row) => row.status === 'failed')
  if (failed.length === 0) return null

  return (
    <ul className="mt-4 grid grid-cols-1 gap-3" aria-label={t('jellyfin.libraries.addPath')}>
      {failed.map((row) => (
        <li key={row.library} className="grid grid-cols-1 gap-2">
          <Notice
            signal="blocked"
            label={t('jellyfin.libraries.pathFailed.title', { library: row.library })}
          >
            <span className="value wrap-anywhere">{row.error}</span>
          </Notice>
          {row.reason && (
            <p className="max-w-prose text-xs text-ink-dim">
              {t(PATH_FAILED[row.reason], { library: row.library, path: row.path, root })}
            </p>
          )}
          {row.reason === 'jellyfin_cannot_see' && (
            <CopyLine command={mountSnippet('jellyfin', root)} />
          )}
        </li>
      ))}
    </ul>
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
      <JellyfinSignInForm
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

/** 管理員帳密那一格。頁 1 在 Berth 的 key 被撤掉時也用它（M4 票 18）。 */
export function JellyfinSignInForm({
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

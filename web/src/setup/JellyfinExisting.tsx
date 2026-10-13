import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { BerthPath, BerthPathFailure, JellyfinConnectInput, JellyfinSetup } from '../api/setup'
import { STICKY_ACTION, Field, Notice, PasswordField, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { failureText } from '../components/failures'
import { MountFix } from '../components/MountFix'
import type { HostDataRoot } from '../components/routeChecks'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { formatList } from '../i18n/list'
import { trimUsername } from './jellyfinUsername'

/** 只關那一個媒體庫的原因 → 那一句。查表而不是動態組 key——動態組過不了 `strictKeyChecks`（票 06）。 */
const PATH_FAILED = {
  directory: 'jellyfin.libraries.pathFailed.directory',
  jellyfin: 'jellyfin.libraries.pathFailed.jellyfin',
  library_missing: 'jellyfin.libraries.pathFailed.library_missing',
} as const satisfies Record<Exclude<BerthPathFailure, 'jellyfin_cannot_see'>, string>

/**
 * 既有 Jellyfin「加入 Berth 路徑」沒加上的那幾個媒體庫（M4 票 19，plan §9.5）。
 *
 * Jellyfin 自己只回 404，原因由 Berth 分辨（`reason`）。**看不到的那一種是整台 Jellyfin 的事**（沒掛
 * `/data`）：合併成一則、列出受影響的媒體庫，補法只給一次（M4 票 63，審計 C5——原本兩個媒體庫就是兩整段、
 * 四個複製鍵）。其餘原因只關那一個媒體庫，一個一條。不給 Jellyfin 的網址：Berth 存的是它自己連得到的
 * 位址（常常是 `host.docker.internal`），瀏覽器開不了。
 */
export function AddPathFailures({
  results,
  root,
  host,
}: {
  results: BerthPath[]
  root: string
  host: HostDataRoot
}) {
  const { t, i18n } = useTranslation()
  const failed = results.filter((row) => row.status === 'failed')
  if (failed.length === 0) return null
  const unseen = failed.filter((row) => row.reason === 'jellyfin_cannot_see')
  const others = failed.filter((row) => row.reason !== 'jellyfin_cannot_see')

  return (
    <ul className="mt-4 grid grid-cols-1 gap-3" aria-label={t('jellyfin.libraries.addPath')}>
      {unseen.length > 0 && (
        <li className="grid grid-cols-1 gap-2">
          <Notice signal="blocked" label={t('jellyfin.libraries.pathFailed.unseenTitle', { root })}>
            {t('jellyfin.libraries.pathFailed.unseen', {
              root,
              libraries: formatList(
                unseen.map((row) => t('common.quoted', { name: row.library })),
                i18n.language,
              ),
            })}
          </Notice>
          <MountFix service="jellyfin" root={root} host={host} />
          <TechnicalDetails lines={unseen.flatMap((row) => [row.path, row.error])} />
        </li>
      )}
      {others.map((row) => (
        <li key={row.library} className="grid grid-cols-1 gap-2">
          <Notice
            signal="blocked"
            label={t('jellyfin.libraries.pathFailed.title', { library: row.library })}
          >
            {/* 人話照 Berth 分出來的原因說；Jellyfin 的原文收進技術細節（M4 票 21）。 */}
            {row.reason && row.reason !== 'jellyfin_cannot_see'
              ? t(PATH_FAILED[row.reason], { library: row.library, path: row.path, root })
              : t('failure.unexpected')}
          </Notice>
          <TechnicalDetails lines={[row.path, row.error]} />
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
  error,
  onConnect,
}: {
  setup: JellyfinSetup
  connecting: boolean
  error: unknown
  onConnect: (input: JellyfinConnectInput) => void
}) {
  return (
    <>
      <JellyfinSignInForm
        connecting={connecting}
        error={error}
        onConnect={onConnect}
        signedIn={setup.api_key_present}
      />
      <ApiKeyFailure setup={setup} />
    </>
  )
}

/** 請求跑完了、換 key 那一步紅了：說 Jellyfin 那一段為什麼沒成（帳密不對、不是管理員…）。 */
export function ApiKeyFailure({ setup }: { setup: JellyfinSetup | undefined }) {
  const { t } = useTranslation()
  const apiKeyStep = setup?.steps.find((row) => row.step === 'api_key')
  if (apiKeyStep?.status !== 'failed') return null

  return (
    <div className="mt-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {failureText(t, apiKeyStep, 'Jellyfin')}
      </Notice>
      <TechnicalDetails lines={[apiKeyStep.error]} />
    </div>
  )
}

/** 管理員帳密那一格。頁 1 在 Berth 的 key 被撤掉時也用它（M4 票 18）。 */
export function JellyfinSignInForm({
  connecting,
  error,
  signedIn,
  onConnect,
}: {
  connecting: boolean
  /** 請求為什麼沒成（`RequestFailed`，M4 票 90）；請求跑完而換 key 那一步紅了是 `ApiKeyFailure` 的事。 */
  error: unknown
  signedIn: boolean
  onConnect: (input: JellyfinConnectInput) => void
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [blank, setBlank] = useState(false)

  function submit(event: FormEvent) {
    event.preventDefault()
    const name = trimUsername(username)
    if (!name || !password) {
      setBlank(true)
      return
    }
    setBlank(false)
    onConnect({ username: name, password })
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 grid max-w-md gap-4">
      <Field
        label={t('jellyfin.existing.username')}
        value={username}
        autoComplete="off"
        error={blank && !trimUsername(username) ? t('owner.error.blank') : undefined}
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
      {error !== null && error !== undefined && (
        <RequestFailed error={error} lead={t('jellyfin.existing.requestFailed')} />
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

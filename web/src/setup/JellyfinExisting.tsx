import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { JellyfinLibrary, JellyfinSetup } from '../api/setup'
import type { SetupStep } from '../api/schemas'
import {
  STICKY_ACTION,
  ConfirmAction,
  CopyLine,
  Field,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'

/**
 * 既有 Jellyfin（plan §9.5）。紅線在這裡是**看得見的**：畫面上沒有「建立媒體庫」，
 * 只有「加入 Berth 路徑」；每個媒體庫的舊路徑照原樣列出來，加的那一條另外標。
 */
export function JellyfinExisting({
  setup,
  signInFailed,
  connecting,
  addingPath,
  installing,
  onConnect,
  onAddPath,
  onInstallPlugin,
}: {
  setup: JellyfinSetup
  signInFailed: boolean
  connecting: boolean
  addingPath: string | null
  installing: boolean
  onConnect: (input: { username: string; password: string }) => void
  onAddPath: (library: string) => void
  onInstallPlugin: () => void
}) {
  const { t } = useTranslation()
  const signedIn = setup.api_key_present
  const apiKeyStep = setup.steps.find((row) => row.step === 'api_key')
  const pluginStep = setup.steps.find((row) => row.step === 'plugin')
  const libraryStep = setup.steps.find((row) => row.step === 'libraries')

  return (
    <>
      <SignInForm
        connecting={connecting}
        failed={signInFailed}
        onConnect={onConnect}
        signedIn={signedIn}
      />

      {apiKeyStep?.status === 'failed' && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            <span className="value break-words">{apiKeyStep.error}</span>
          </Notice>
        </div>
      )}

      {signedIn && (
        <>
          <Libraries
            libraries={setup.libraries}
            addingPath={addingPath}
            failure={libraryStep?.status === 'failed' ? libraryStep : undefined}
            baseUrl={setup.base_url}
            onAddPath={onAddPath}
          />

          <section className="mt-8 border-t-2 border-rule pt-6">
            <h3 className="text-sm font-semibold text-ink">{t('jellyfin.plugin.title')}</h3>
            <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('jellyfin.plugin.lede')}</p>
            <div className="mt-3">
              {setup.merge_versions_installed ? (
                <Notice signal="secured" label={t('jellyfin.cutaway.installed')}>
                  {t('jellyfin.plugin.already', {
                    version: pluginStep?.detail || '',
                    movies: setup.merge_movies_task_id,
                    episodes: setup.merge_episodes_task_id,
                  })}
                </Notice>
              ) : (
                <ConfirmAction
                  label={t('jellyfin.plugin.install')}
                  confirmLabel={t('jellyfin.plugin.confirm')}
                  warning={t('jellyfin.plugin.warning')}
                  pending={installing}
                  pendingLabel={t('jellyfin.plugin.installing')}
                  onConfirm={onInstallPlugin}
                />
              )}
            </div>
            {pluginStep?.status === 'failed' && (
              <div className="mt-3 grid grid-cols-1 gap-2">
                <Notice signal="blocked" label={t('common.failed')}>
                  <span className="value break-words">{pluginStep.error}</span>
                </Notice>
                <CopyLine command={`${setup.base_url}/web/#/dashboard/plugins/repositories`} />
              </div>
            )}
          </section>
        </>
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
  onConnect: (input: { username: string; password: string }) => void
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
        error={blank && !username.trim() ? t('admin.error.blank') : undefined}
        onChange={(event) => setUsername(event.target.value)}
      />
      <PasswordField
        label={t('jellyfin.existing.password')}
        value={password}
        autoComplete="off"
        hint={t('jellyfin.existing.passwordHint')}
        error={blank && !password ? t('admin.error.blank') : undefined}
        onChange={(event) => setPassword(event.target.value)}
      />
      {failed && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('jellyfin.existing.requestFailed')}
        </Notice>
      )}
      <div className={STICKY_ACTION}>
        <PrimaryButton type="submit" disabled={connecting}>
          {connecting
            ? t('jellyfin.existing.signingIn')
            : t(signedIn ? 'jellyfin.existing.signInAgain' : 'jellyfin.existing.signIn')}
        </PrimaryButton>
      </div>
    </form>
  )
}

function Libraries({
  libraries,
  addingPath,
  failure,
  baseUrl,
  onAddPath,
}: {
  libraries: JellyfinLibrary[]
  addingPath: string | null
  /** 上一次「加入 Berth 路徑」失敗的那一步。原文與手動步驟就地攤開。 */
  failure: SetupStep | undefined
  baseUrl: string
  onAddPath: (library: string) => void
}) {
  const { t } = useTranslation()

  return (
    <section className="mt-8 border-t-2 border-rule pt-6">
      <h3 className="text-sm font-semibold text-ink">{t('jellyfin.libraries.title')}</h3>
      <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('jellyfin.libraries.lede')}</p>

      {failure && (
        <div className="mt-4 grid grid-cols-1 gap-2">
          <Notice signal="blocked" label={t('common.failed')}>
            <span className="value break-words">{failure.error}</span>
          </Notice>
          <p className="max-w-prose text-xs text-ink-dim">{t('jellyfin.libraries.addFailed')}</p>
          <CopyLine command={`${baseUrl}/web/#/dashboard/libraries`} />
        </div>
      )}

      {libraries.length === 0 ? (
        <div className="mt-4">
          <Notice signal="assigned" label={t('jellyfin.libraries.emptyLabel')}>
            {t('jellyfin.libraries.empty')}
          </Notice>
        </div>
      ) : (
        <ul className="mt-4 grid gap-3">
          {libraries.map((library) => (
            <LibraryRow
              key={library.name}
              library={library}
              adding={addingPath === library.name}
              onAddPath={onAddPath}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function LibraryRow({
  library,
  adding,
  onAddPath,
}: {
  library: JellyfinLibrary
  adding: boolean
  onAddPath: (library: string) => void
}) {
  const { t } = useTranslation()

  return (
    <li className="min-w-0 border-2 border-rule bg-well">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span
          className={`label px-2 py-1.5 ${
            SIGNAL_FILL[library.has_berth_path ? 'secured' : 'assigned']
          }`}
        >
          {t(library.has_berth_path ? 'jellyfin.libraries.wired' : 'jellyfin.libraries.unwired')}
        </span>
        <span className="value text-sm font-semibold text-ink">{library.name}</span>
        <span className="label ml-auto text-ink-dim">{library.collection_type || '—'}</span>
      </div>

      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 border-t-2 border-rule px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <dt className="label self-center text-ink-dim">{t('jellyfin.libraries.paths')}</dt>
        <dd className="value min-w-0 text-sm text-ink">
          {library.locations.map((path) => (
            <span key={path} className="block break-all">
              {path}
              {path === library.berth_path && (
                <span className="label ml-2 text-ink-dim">{t('jellyfin.libraries.berthPath')}</span>
              )}
            </span>
          ))}
        </dd>
        <dt className="label mt-1 self-center text-ink-dim">{t('jellyfin.libraries.fetchers')}</dt>
        <dd className="value mt-1 min-w-0 break-words text-sm text-ink">
          {library.metadata_fetchers.join(' · ') || '—'}
        </dd>
      </dl>

      {library.uses_tvdb && (
        <div className="border-t-2 border-rule px-4 py-3">
          <Notice signal="assigned" label={t('jellyfin.libraries.warningLabel')}>
            {t('jellyfin.libraries.tvdb')}
          </Notice>
        </div>
      )}

      {!library.has_berth_path && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p className="label text-ink-dim">{t('jellyfin.libraries.willAdd')}</p>
          <div className="mt-2">
            <CopyLine command={library.berth_path} />
          </div>
          <div className="mt-3">
            <ConfirmAction
              label={t('jellyfin.libraries.addPath')}
              confirmLabel={t('jellyfin.libraries.addConfirm')}
              warning={t('jellyfin.libraries.addWarning', {
                library: library.name,
                path: library.berth_path,
              })}
              pending={adding}
              pendingLabel={t('jellyfin.libraries.adding')}
              onConfirm={() => onAddPath(library.name)}
            />
          </div>
        </div>
      )}
    </li>
  )
}

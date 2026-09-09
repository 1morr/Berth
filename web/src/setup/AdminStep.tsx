import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { AdminInput, SetupStatus } from '../api/setup'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import {
  STICKY_ACTION,
  Checkbox,
  Field,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'

/**
 * 第 1 步：建立 Berth 管理員（plan §9.3）。
 *
 * 左邊的剖面是活的——帳號與勾選一改，「將會寫入」立刻跟著改。套用前後看同一個剖面。
 */
export function AdminStep({
  status,
  pending,
  failed,
  onSubmit,
}: {
  status: SetupStatus
  pending: boolean
  failed: boolean
  onSubmit: (input: AdminInput) => void
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState(status.admin_username)
  const [password, setPassword] = useState('')
  const [applyToServices, setApplyToServices] = useState(status.apply_to_services)
  const [blank, setBlank] = useState(false)

  const account = username.trim() || '—'
  const spread = applyToServices ? account : t('admin.cutaway.skipped')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!username.trim() || !password) {
      setBlank(true)
      return
    }
    setBlank(false)
    onSubmit({ username: username.trim(), password, apply_to_services: applyToServices })
  }

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <Cutaway title={t('admin.cutaway.title')}>
            <CutawayRow term={t('admin.cutaway.berth')} value={account} />
            <CutawayRow term={t('admin.cutaway.jellyfin')} value={account} />
            <CutawayRow
              term={t('admin.cutaway.qbittorrent')}
              value={spread}
              muted={!applyToServices}
            />
            <CutawayRow
              term={t('admin.cutaway.prowlarr')}
              value={spread}
              muted={!applyToServices}
            />
          </Cutaway>
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('admin.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('admin.lede')}</p>

        <form onSubmit={submit} noValidate className="mt-6 grid gap-5">
          <Field
            label={t('admin.field.username')}
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            error={blank && !username.trim() ? t('admin.error.blank') : undefined}
          />
          <PasswordField
            label={t('admin.field.password')}
            value={password}
            autoComplete="new-password"
            onChange={(event) => setPassword(event.target.value)}
            error={blank && !password ? t('admin.error.blank') : undefined}
          />
          <Checkbox
            label={t('admin.field.apply')}
            hint={t('admin.field.applyHint')}
            checked={applyToServices}
            onChange={setApplyToServices}
          />
          <div className={STICKY_ACTION}>
            <PrimaryButton type="submit" disabled={pending}>
              {pending ? t('admin.submitting') : t('admin.submit')}
            </PrimaryButton>
          </div>
          {failed && (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('admin.error.failed')}
            </Notice>
          )}
        </form>
      </div>
    </div>
  )
}

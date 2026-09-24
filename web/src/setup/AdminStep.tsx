import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { AdminInput, SetupStatus } from '../api/setup'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { adminCutaway, detectedOrigin, type CutawayLine } from './adminCutaway'
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
 * 剖面照第 2 步的判定說話（`adminCutaway`，票 06c）：偵測之前不斷定哪個服務會被寫入。
 *
 * **帳號交給 Jellyfin 之後**（`jellyfin_owns_account`）這一步只改得動 qBittorrent 與 Prowlarr
 * 介面那一組：Berth 改不了 Jellyfin 的密碼（Seerr 的慣例：媒體伺服器的管理員就是帳號的主人）。
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
  const owned = status.jellyfin_owns_account
  const [username, setUsername] = useState(
    owned ? status.interface_username : status.admin_username,
  )
  const [password, setPassword] = useState('')
  const [applyToServices, setApplyToServices] = useState(status.apply_to_services)
  const [blank, setBlank] = useState(false)

  const rows = adminCutaway({
    services: status.services,
    owned,
    applied: applyToServices,
    typed: username.trim() || '—',
    owner: status.admin_username,
  })
  const sentence = (line: CutawayLine) => t(line.key, { account: line.account })
  const words = owned
    ? {
        title: t('admin.owned.title'),
        lede: t('admin.owned.lede'),
        username: t('admin.owned.username'),
        password: t('admin.owned.password'),
        applyHint: t('admin.owned.applyHint'),
        submit: pending ? t('admin.owned.submitting') : t('admin.owned.submit'),
      }
    : {
        title: t('admin.title'),
        lede: t('admin.lede'),
        username: t('admin.field.username'),
        password: t('admin.field.password'),
        applyHint: t('admin.field.applyHint'),
        submit: pending ? t('admin.submitting') : t('admin.submit'),
      }

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
            {(['berth', 'jellyfin', 'qbittorrent', 'prowlarr'] as const).map((row) => (
              <CutawayRow
                key={row}
                term={t(`admin.cutaway.${row}`)}
                value={sentence(rows[row])}
                muted={rows[row].muted}
              />
            ))}
          </Cutaway>
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{words.title}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{words.lede}</p>
        {owned && (
          <div className="mt-4 max-w-prose">
            <Notice signal="secured" label={t('admin.owned.label')}>
              {detectedOrigin(status.services, 'jellyfin') === 'existing'
                ? t('admin.owned.existing')
                : t('admin.owned.bundled', { account: status.admin_username })}
            </Notice>
          </div>
        )}

        <form onSubmit={submit} noValidate className="mt-6 grid gap-5">
          <Field
            label={words.username}
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            error={blank && !username.trim() ? t('admin.error.blank') : undefined}
          />
          <PasswordField
            label={words.password}
            value={password}
            autoComplete="new-password"
            onChange={(event) => setPassword(event.target.value)}
            error={blank && !password ? t('admin.error.blank') : undefined}
          />
          <Checkbox
            label={t('admin.field.apply')}
            hint={words.applyHint}
            checked={applyToServices}
            onChange={setApplyToServices}
          />
          <div className={STICKY_ACTION}>
            <PrimaryButton type="submit" busy={pending}>
              {words.submit}
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

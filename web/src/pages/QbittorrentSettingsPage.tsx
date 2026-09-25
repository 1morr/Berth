import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { issuesQueryOptions } from '../api/issues'
import { reviewQueryOptions } from '../api/review'
import type { QbittorrentSetup } from '../api/schemas'
import {
  diskQueryOptions,
  qbittorrentDriftQueryOptions,
  restoreQbittorrent,
  saveDisk,
} from '../api/settings'
import { Field, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { ServiceConnection } from '../settings/ServiceConnection'
import { HealthSection } from '../settings/HealthSection'
import { useServiceCheck } from '../settings/useServiceCheck'

/**
 * 設定 → qBittorrent（票 06i）。健康與重新檢查、既有 qBittorrent 的位址與帳密（精靈第 2 步的
 * 同一條纜繩）、建議設定的差異與還原（brief §16.3），以及磁碟空間門檻。
 *
 * 門檻住這裡（shape 時使用者拍板）：它量的是 qBittorrent 的 incomplete 那一側，擋的是送單給
 * qBittorrent（M3 票 04），不必為一個欄位多開一個「一般」分頁。
 */
export function QbittorrentSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const check = useServiceCheck()
  const drift = useQuery(qbittorrentDriftQueryOptions)

  const restore = useMutation({
    mutationFn: restoreQbittorrent,
    onSuccess: (fresh) => {
      queryClient.setQueryData(qbittorrentDriftQueryOptions.queryKey, fresh)
      // 還原之後那個服務的漂移旗標要跟著清掉，所以順便重測它。
      check.mutate('qbittorrent')
    },
  })

  return (
    <SettingsFrame
      title={t('settings.qbittorrentPage.title')}
      lede={t('settings.qbittorrentPage.lede')}
    >
      <HealthSection kind="qbittorrent" check={check} />
      <ServiceConnection
        kind="qbittorrent"
        onConnected={() => {
          check.mutate('qbittorrent')
          // 換了一台或換了帳密，差異表讀的是新的那一台。
          void queryClient.invalidateQueries({ queryKey: qbittorrentDriftQueryOptions.queryKey })
        }}
      />
      <Drift
        drift={drift.data}
        pending={drift.isPending}
        restoring={restore.isPending}
        failed={restore.isError}
        onRestore={() => restore.mutate()}
      />
      <DiskThreshold />
    </SettingsFrame>
  )
}

/**
 * 磁碟空間門檻（M2 票 09c，2026-09-23 使用者拍板）。形狀照 Sonarr 的 Minimum Free Space（一個
 * 全域數字），單位是 GB：Berth 以硬鏈接入庫不佔空間，吃空間的是下載。
 *
 * 後端存完**立刻重量一次**，所以待處理清單與審核佇列一起重問——改完門檻的那一刻 `/issues`
 * 就是新的答案。不是 0 以上整數的值由欄位自己說不行，不送出去。
 */
function DiskThreshold() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const current = useQuery(diskQueryOptions)
  const [draft, setDraft] = useState<string | null>(null)
  const value = draft ?? (current.data ? String(current.data.min_free_gb) : '')
  const valid = /^\d+$/.test(value.trim())

  const save = useMutation({
    mutationFn: () => saveDisk(Number(value.trim())),
    onSuccess: (fresh) => {
      queryClient.setQueryData(diskQueryOptions.queryKey, fresh)
      void queryClient.invalidateQueries({ queryKey: issuesQueryOptions().queryKey })
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      setDraft(null)
    },
  })
  const invalid =
    (draft !== null && !valid) || (save.error instanceof ApiError && save.error.status === 422)

  return (
    <SettingsSection
      id="settings-disk"
      title={t('settings.disk.title')}
      lede={t('settings.disk.lede')}
    >
      <form
        noValidate
        className="grid gap-3 sm:max-w-xs"
        onSubmit={(event) => {
          event.preventDefault()
          if (valid) save.mutate()
        }}
      >
        <Field
          label={t('settings.disk.label')}
          type="text"
          inputMode="numeric"
          value={value}
          onChange={(event) => setDraft(event.target.value)}
          hint={t('settings.disk.hint')}
          error={invalid ? t('settings.disk.invalid') : undefined}
        />
        <div className="flex flex-wrap items-center gap-3">
          <GhostButton type="submit" busy={save.isPending}>
            {save.isPending ? t('settings.disk.saving') : t('settings.disk.save')}
          </GhostButton>
          <p aria-live="polite" className="text-xs text-ink-dim">
            {save.isSuccess ? t('settings.disk.saved') : ''}
          </p>
        </div>
        {save.isError && !invalid && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.disk.failed')}
          </Notice>
        )}
      </form>
    </SettingsSection>
  )
}

/**
 * qBittorrent 的建議設定漂移（brief §16.3）。
 *
 * 剖面是一張逐鍵的差異表（鍵 / 現值 / 建議值），不是散文——鍵名用 `app/setPreferences`
 * 的原字串，使用者在 qBittorrent 自己的介面上也找得到它（票 08 的決定）。
 */
function Drift({
  drift,
  pending,
  restoring,
  failed,
  onRestore,
}: {
  drift: QbittorrentSetup | undefined
  pending: boolean
  restoring: boolean
  failed: boolean
  onRestore: () => void
}) {
  const { t } = useTranslation()
  const changed = drift?.diffs.filter((row) => row.differs) ?? []

  return (
    <SettingsSection id="settings-drift" title={t('settings.drift.title')}>
      {pending && <p className="text-xs text-ink-dim">{t('health.checking')}</p>}

      {drift && !drift.reachable && (
        <div>
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.drift.unreachable')}
          </Notice>
        </div>
      )}

      {drift?.reachable && (
        <>
          <p className="text-xs text-ink-dim">
            {changed.length === 0
              ? t('settings.drift.clean')
              : t('settings.drift.changed', { count: changed.length })}
          </p>

          <div className="mt-3 border-2 border-rule bg-well">
            {/* 路徑很長（容器裡是 `/data/...`，本機演練是暫存目錄），所以讓它換行而不是
                橫向捲動——被切掉的建議值等於沒顯示。 */}
            <table className="w-full table-fixed border-collapse text-xs">
              <thead>
                <tr className="border-b-2 border-rule bg-deck">
                  <th scope="col" className="label px-3 py-2 text-left text-ink-dim">
                    {t('settings.drift.key')}
                  </th>
                  <th scope="col" className="label px-3 py-2 text-left text-ink-dim">
                    {t('settings.drift.current')}
                  </th>
                  <th scope="col" className="label px-3 py-2 text-left text-ink-dim">
                    {t('settings.drift.recommended')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {drift.diffs.map((row) => (
                  <tr key={row.key} className="border-b border-rule last:border-0">
                    <td className="value wrap-anywhere px-3 py-2 text-ink">{row.key}</td>
                    <td
                      className={`value wrap-anywhere px-3 py-2 ${
                        row.differs ? 'text-blocked-ink' : 'text-ink-dim'
                      }`}
                    >
                      {/* 顏色不是唯一的編碼（PRODUCT.md 的無障礙底線）：被改過的那一列
                          自己說出來，不看顏色也讀得出哪幾個鍵要還原。 */}
                      {row.differs && (
                        <span className={`label mr-2 px-1.5 py-0.5 ${SIGNAL_FILL.assigned}`}>
                          {t('settings.drift.changedKey')}
                        </span>
                      )}
                      {row.current || '—'}
                    </td>
                    <td className="value wrap-anywhere px-3 py-2 text-ink">{row.recommended}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {changed.length > 0 && (
            <div className="mt-4 grid gap-3 sm:max-w-xs">
              <PrimaryButton type="button" busy={restoring} onClick={onRestore}>
                {restoring ? t('settings.drift.restoring') : t('settings.drift.restore')}
              </PrimaryButton>
            </div>
          )}

          {failed && (
            <div className="mt-4">
              <Notice signal="blocked" label={t('common.failed')}>
                {t('settings.drift.restoreFailed')}
              </Notice>
            </div>
          )}
        </>
      )}
    </SettingsSection>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { issuesQueryOptions } from '../api/issues'
import { reviewQueryOptions } from '../api/review'
import { routesQueryOptions } from '../api/routes'
import { qbittorrentSetupQueryOptions, setQbittorrentLogin } from '../api/setup'
import { diskQueryOptions, saveDisk } from '../api/settings'
import { Field, GhostButton, Notice } from '../components/controls'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { ServiceConnection } from '../settings/ServiceConnection'
import { HealthSection } from '../settings/HealthSection'
import { InterfaceLoginSection } from '../settings/InterfaceLoginSection'
import { useServiceCheck } from '../settings/useServiceCheck'
import { PROGRESS_INTERVAL_MS, useRecheckRoutes } from '../settings/recheckRoutes'
import { RouteRecheck } from '../settings/RouteRecheck'

/**
 * 設定 → qBittorrent（票 06i）。健康與重新檢查、既有 qBittorrent 的位址與帳密（精靈第 2 步的
 * 同一條纜繩）、套件內那一台的 WebUI 登入（M4 票 07），以及磁碟空間門檻。Berth 不寫也不看它的
 * 全域偏好（M4 票 32），所以這一頁沒有「建議設定」。
 *
 * **換了一台之後自動重查每一條 Route**（M4 票 59，審計 S4）：分類建在原本那一台，健康頁的 Route 那一格
 * 會停在「要重新檢查」。存下的那一台測過了就送一次「全部重新檢查」；套件內那一台還在啟動的話，等之後的
 * 重新測試轉綠再送（`armed`）。同一台只改帳密不重查。
 *
 * 門檻住這裡（shape 時使用者拍板）：它量的是 qBittorrent 的 incomplete 那一側，擋的是送單給
 * qBittorrent（M3 票 04），不必為一個欄位多開一個「一般」分頁。
 */
export function QbittorrentSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const check = useServiceCheck()
  const qbittorrent = useQuery(qbittorrentSetupQueryOptions)
  const recheck = useRecheckRoutes()
  // 換了一台而那一台還沒測過（套件內的還在啟動）：等它轉綠再重查。
  const [armed, setArmed] = useState(false)
  // 跑著的時候照頁 3 的節奏重讀每一條跑到哪裡（M4 票 43）。
  const routes = useQuery({
    ...routesQueryOptions,
    refetchInterval: recheck.isPending ? PROGRESS_INTERVAL_MS : false,
  })

  const login = useMutation({
    mutationFn: setQbittorrentLogin,
    onSuccess: (fresh) => {
      queryClient.setQueryData(qbittorrentSetupQueryOptions.queryKey, fresh)
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
        onConnected={(next, moved) => {
          check.mutate('qbittorrent')
          // 換了一台或換了帳密，登入那一區讀的是新的那一台。
          void queryClient.invalidateQueries({ queryKey: qbittorrentSetupQueryOptions.queryKey })
          const ok = next.services.some((row) => row.kind === 'qbittorrent' && row.state === 'ok')
          // 只在換了一台時重查：同一台改帳密不會作廢 Route 的檢查（`forget_route_checks` 只看 `moved`），
          // 而重查會問探針，每一條都可能觸發它的「完成時執行外部程式」（M4 票 19）。
          if (ok && (moved || armed)) {
            setArmed(false)
            recheck.mutate()
          } else if (moved) {
            setArmed(true)
          }
        }}
      />
      <RouteRecheck recheck={recheck} routes={routes.data?.map((row) => row.route)} />
      {/* 連不上時照樣畫：按下去得到的是服務回的原文，不是一個消失的區塊。 */}
      {qbittorrent.data?.web_ui_login && (
        <InterfaceLoginSection
          service="qbittorrent"
          current={qbittorrent.data.web_ui_username}
          saving={login.isPending}
          onSave={async (value) => {
            const fresh = await login.mutateAsync(value)
            return {
              step: fresh.steps.find((row) => row.step === 'web_ui_password'),
              error: fresh.error,
            }
          }}
        />
      )}
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

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import { ApiError } from '../api/client'
import type { JellyfinWeb } from '../api/jellyfin'
import { jellyfinAddressQueryOptions, saveJellyfinAddress } from '../api/settings'
import {
  connectJellyfin,
  jellyfinSetupQueryOptions,
  setupStatusQueryOptions,
  type JellyfinConnectInput,
} from '../api/setup'
import { Field, GhostButton, Notice } from '../components/controls'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { ServiceConnection } from '../settings/ServiceConnection'
import { HealthSection } from '../settings/HealthSection'
import { useServiceCheck, type ServiceCheck } from '../settings/useServiceCheck'
import { JellyfinSignIn } from '../setup/JellyfinExisting'

/**
 * 設定 → Jellyfin（票 06i）。健康與重新檢查、既有 Jellyfin 的位址與重新登入（精靈第 2、3 步的
 * 同一批元件與命令），以及對外網址（票 13）。
 *
 * 套件內 Jellyfin 的媒體庫清單（06f）不在這裡：建好的媒體庫改名刪除在 Jellyfin，
 * Route 在媒體庫路徑那一頁（`.scratch/m3/settings-shape.md` 的「不做」）。
 */
export function JellyfinSettingsPage() {
  const { t } = useTranslation()
  const check = useServiceCheck()

  return (
    <SettingsFrame title={t('settings.jellyfinPage.title')} lede={t('settings.jellyfinPage.lede')}>
      <HealthSection kind="jellyfin" check={check} />
      <ServiceConnection kind="jellyfin" onConnected={() => check.mutate('jellyfin')} />
      <SignIn check={check} />
      <JellyfinAddress />
    </SettingsFrame>
  )
}

/**
 * 重新登入換一把 API key。只有既有的 Jellyfin 有：套件內那一台的 key 是精靈在靠泊時
 * 自己建的，使用者手上沒有那個管理員要登入的理由。
 */
function SignIn({ check }: { check: ServiceCheck }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const status = useQuery(setupStatusQueryOptions)
  const existing =
    status.data?.services.find((row) => row.kind === 'jellyfin')?.origin === 'existing'
  const setup = useQuery({ ...jellyfinSetupQueryOptions, enabled: existing })

  const signIn = useMutation({
    mutationFn: (input: JellyfinConnectInput) => connectJellyfin(input),
    onSuccess: (next) => {
      queryClient.setQueryData(jellyfinSetupQueryOptions.queryKey, next)
      check.mutate('jellyfin')
    },
  })

  if (!existing || !setup.data) return null

  return (
    <SettingsSection
      id="settings-jellyfin-sign-in"
      title={t('settings.jellyfinPage.signIn.title')}
      lede={t('settings.jellyfinPage.signIn.lede')}
    >
      <JellyfinSignIn
        setup={setup.data}
        connecting={signIn.isPending}
        failed={signIn.isError}
        onConnect={(input) => signIn.mutate(input)}
      />
    </SettingsSection>
  )
}

/**
 * Jellyfin 的對外網址（票 13，使用者拍板：選填 + 自動推導，Seerr 的 `externalHostname` 慣例）。
 *
 * 欄位底下永遠說得出「現在深連結開在哪」——空著的時候那一句就是推導的結果，所以管理員不必
 * 先猜「不填會怎樣」。不是 http(s) 的位址由後端擋（422），說不行的是欄位自己（票 02b 的規則）。
 */
function JellyfinAddress() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const current = useQuery(jellyfinAddressQueryOptions)
  // `null` 是「這一輪還沒動過」，那時欄位跟著伺服器上的值走。
  const [draft, setDraft] = useState<string | null>(null)
  const value = draft ?? current.data?.public_url ?? ''

  const save = useMutation({
    mutationFn: () => saveJellyfinAddress(value),
    onSuccess: (fresh) => {
      queryClient.setQueryData(jellyfinAddressQueryOptions.queryKey, fresh)
      // 媒體庫的牆帶著同一份主機，下一次打開要是新的那一個。
      void queryClient.invalidateQueries({ queryKey: ['inventory'] })
      setDraft(null)
    },
  })
  const rejected = save.error instanceof ApiError && save.error.status === 422

  return (
    <SettingsSection
      id="settings-jellyfin"
      title={t('settings.jellyfin.title')}
      lede={t('settings.jellyfin.lede')}
    >
      <form
        noValidate
        className="grid gap-3 sm:max-w-md"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <Field
          label={t('settings.jellyfin.label')}
          type="url"
          inputMode="url"
          value={value}
          placeholder={t('settings.jellyfin.placeholder')}
          onChange={(event) => setDraft(event.target.value)}
          hint={current.data ? whereLinksOpen(current.data, t) : undefined}
          error={rejected ? t('settings.jellyfin.invalid') : undefined}
        />
        <div className="flex flex-wrap items-center gap-3">
          <GhostButton type="submit" busy={save.isPending}>
            {save.isPending ? t('settings.jellyfin.saving') : t('settings.jellyfin.save')}
          </GhostButton>
          <p aria-live="polite" className="text-xs text-ink-dim">
            {save.isSuccess ? t('settings.jellyfin.saved') : ''}
          </p>
        </div>
        {save.isError && !rejected && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.jellyfin.failed')}
          </Notice>
        )}
      </form>
    </SettingsSection>
  )
}

/** 欄位底下那一句：填了的是它，沒填的是推導出來的哪一台（`services/deeplink.py`）。 */
function whereLinksOpen(web: JellyfinWeb, t: TFunction): string {
  if (web.public_url) return t('settings.jellyfin.set', { url: web.public_url })
  if (web.url) return t('settings.jellyfin.derivedUrl', { url: web.url })
  if (web.port !== null) return t('settings.jellyfin.derivedHost', { port: web.port })
  return t('settings.jellyfin.unknown')
}

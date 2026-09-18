import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import { ApiError } from '../api/client'
import { healthDetailQueryOptions, healthQueryOptions, type HealthDetail } from '../api/health'
import type { JellyfinWeb } from '../api/jellyfin'
import type { QbittorrentSetup, ServiceKind } from '../api/schemas'
import {
  jellyfinAddressQueryOptions,
  qbittorrentDriftQueryOptions,
  restoreQbittorrent,
  saveJellyfinAddress,
  servicesQueryOptions,
  testService,
} from '../api/settings'
import { berthNumberOf } from '../components/berths'
import { Field, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { SIGNAL_FILL } from '../components/signal'
import { SettingsTabs } from '../components/SettingsTabs'
import { ServiceCard } from '../health/ServiceCard'

/**
 * 服務設定頁 `/settings/services`（票 10、`.scratch/m0/health-shape.md`）。只有 admin 進得來。
 *
 * 這一頁只有兩件事，因為**位址與憑證仍然在精靈裡改**——精靈跑完之後它就是設定入口
 * （plan §6），複製四份連線表單只會讓兩份規則分岔：
 *
 * 1. 逐服務「測試連線」：立刻重測那一個，結果就是健康頁上那一列。
 * 2. qBittorrent 的「還原建議設定」：關鍵設定漂移時把它們寫回去（brief §16.3）。
 */
export function ServiceSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const services = useQuery(servicesQueryOptions)
  const drift = useQuery(qbittorrentDriftQueryOptions)

  /** 測試與還原都會改健康狀態，所以兩份快取一起換掉（健康頁看的是同一份資料）。 */
  function remember(fresh: HealthDetail) {
    queryClient.setQueryData(servicesQueryOptions.queryKey, fresh)
    queryClient.setQueryData(healthDetailQueryOptions.queryKey, fresh)
    // `void`：匿名的那一支重抓完之前按鈕不必一直轉，回傳的 promise 是刻意不等的。
    void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey, exact: true })
  }

  const test = useMutation({
    mutationFn: (kind: ServiceKind) => testService(kind),
    onSuccess: remember,
  })

  const restore = useMutation({
    mutationFn: restoreQbittorrent,
    onSuccess: (fresh) => {
      queryClient.setQueryData(qbittorrentDriftQueryOptions.queryKey, fresh)
      // 還原之後那個服務的漂移旗標要跟著清掉，所以順便重測它。
      test.mutate('qbittorrent')
    },
  })

  if (services.isPending) {
    return <p className="px-6 py-8 text-sm text-ink-dim">{t('health.checking')}</p>
  }

  if (!services.data) {
    return (
      <div className="px-6 py-8">
        <Notice signal="blocked" label={t('common.failed')}>
          {t('health.unreachable')}
        </Notice>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <SettingsTabs />
      <h2 className="value mt-6 text-lg font-semibold text-ink">{t('settings.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('settings.lede')}</p>

      <div className="mt-6 grid gap-4">
        {services.data.services.map((row) => (
          <ServiceCard
            key={row.kind}
            row={row}
            actions={
              <>
                <GhostButton
                  type="button"
                  disabled={test.isPending}
                  onClick={() => test.mutate(row.kind)}
                >
                  {test.isPending && test.variables === row.kind
                    ? t('settings.testing')
                    : t('settings.test')}
                </GhostButton>
                <Link
                  to="/setup"
                  search={{ berth: berthNumberOf(row.kind) }}
                  className="label self-center text-ink-dim underline hover:text-ink"
                >
                  {t('settings.editHint')}
                </Link>
              </>
            }
          />
        ))}
      </div>

      {test.isError && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.testFailed')}
          </Notice>
        </div>
      )}

      <JellyfinAddress />

      <Drift
        drift={drift.data}
        pending={drift.isPending}
        restoring={restore.isPending}
        failed={restore.isError}
        onRestore={() => restore.mutate()}
      />
    </div>
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
    <section className="mt-8" aria-labelledby="settings-jellyfin">
      <h3 id="settings-jellyfin" className="value text-sm font-semibold text-ink">
        {t('settings.jellyfin.title')}
      </h3>
      <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('settings.jellyfin.lede')}</p>

      <form
        noValidate
        className="mt-3 grid gap-3 sm:max-w-md"
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
          <GhostButton type="submit">
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
    </section>
  )
}

/** 欄位底下那一句：填了的是它，沒填的是推導出來的哪一台（`services/deeplink.py`）。 */
function whereLinksOpen(web: JellyfinWeb, t: TFunction): string {
  if (web.public_url) return t('settings.jellyfin.set', { url: web.public_url })
  if (web.url) return t('settings.jellyfin.derivedUrl', { url: web.url })
  if (web.port !== null) return t('settings.jellyfin.derivedHost', { port: web.port })
  return t('settings.jellyfin.unknown')
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
    <section className="mt-8" aria-labelledby="settings-drift">
      <h3 id="settings-drift" className="value text-sm font-semibold text-ink">
        {t('settings.drift.title')}
      </h3>

      {pending && <p className="mt-3 text-xs text-ink-dim">{t('health.checking')}</p>}

      {drift && !drift.reachable && (
        <div className="mt-3">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.drift.unreachable')}
          </Notice>
        </div>
      )}

      {drift?.reachable && (
        <>
          <p className="mt-2 text-xs text-ink-dim">
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
              <PrimaryButton type="button" disabled={restoring} onClick={onRestore}>
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
    </section>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { healthDetailQueryOptions, healthQueryOptions } from '../api/health'
import {
  applyIndexers,
  indexerSetupQueryOptions,
  removeIndexer,
  retestService,
  searchIndexers,
  setIndexerLogin,
  setupStatusQueryOptions,
  skipIndexers,
  testIndexers,
  type IndexerSetup,
} from '../api/setup'
import { RequestFailed } from '../components/RequestFailed'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { HealthSection } from '../settings/HealthSection'
import { IndexerSetAside, IndexerUnused } from '../settings/IndexerUsage'
import { InterfaceLoginSection } from '../settings/InterfaceLoginSection'
import { ServiceConnection } from '../settings/ServiceConnection'
import { useServiceCheck } from '../settings/useServiceCheck'
import { IndexerActions } from '../setup/IndexerStep'

/**
 * 設定 → Prowlarr（票 06i）。進來只讀（M4 票 09：不測任何一站）；測試、加站、試搜、移除都由人按——
 * 精靈頁 4 的那一批元件（`IndexerSites`）與同一批 `setup/indexers/*` 命令。
 * 來源、位址與 key 是另兩頁同一個連線區（`ServiceConnection`，M4 票 39：與精靈同一支
 * `POST /setup/services/prowlarr`）。套件內 Prowlarr 的介面登入是自己的一區（M4 票 07）：加站不帶
 * 登入，登入在這裡改。
 *
 * 健康卡是 Prowlarr 那一張（plan §3.2）。
 *
 * **可以不用 Prowlarr**（M4 票 61，`.scratch/m4/prowlarr-optional-shape.md`）：就是精靈頁 4 的「之後再說」，
 * 同一支 `POST /setup/indexers/skip`。不用時整頁收成一塊（`IndexerUnused`），在用時頁尾一區
 * （`IndexerSetAside`）。用不用讀健康那一列的 `unused`：它不連任何服務，而站的清單要現場問 Prowlarr——
 * 不用的時候不該問。
 */
export function IndexerSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const check = useServiceCheck()
  const health = useQuery(healthDetailQueryOptions)
  const unused = health.data?.services.find((row) => row.kind === 'prowlarr')?.unused === true
  const indexers = useQuery({ ...indexerSetupQueryOptions, enabled: health.isFetched && !unused })

  /** 站的清單變了：試搜的結果是舊清單的，健康那一項也重測（它報的是站數）。 */
  function absorb(next: IndexerSetup) {
    queryClient.setQueryData(indexerSetupQueryOptions.queryKey, next)
    check.mutate('prowlarr')
  }

  /** 換了一台、換了 key 或重讀了 key：站的清單與介面登入那一區讀的是新的那一台，健康卡也重測。 */
  function reconnected() {
    check.mutate('prowlarr')
    void queryClient.invalidateQueries({ queryKey: indexerSetupQueryOptions.queryKey })
  }

  const usage = useMutation({
    mutationFn: skipIndexers,
    onSuccess: async (next) => {
      queryClient.setQueryData(indexerSetupQueryOptions.queryKey, next)
      void queryClient.invalidateQueries({ queryKey: healthQueryOptions.queryKey, exact: true })
      // 改回來就真的連一次：健康卡要說 Prowlarr 現在的樣子，不是選不用之前那一輪。不用的那一刻不連它，
      // 重讀健康那一份就是「沒有使用」。
      if (next.skipped) {
        await queryClient.invalidateQueries({ queryKey: healthDetailQueryOptions.queryKey })
      } else {
        await check.mutateAsync('prowlarr')
      }
    },
  })
  const apply = useMutation({ mutationFn: applyIndexers, onSuccess: absorb })
  const remove = useMutation({ mutationFn: removeIndexer, onSuccess: absorb })
  const login = useMutation({ mutationFn: setIndexerLogin, onSuccess: absorb })
  // 清單讀不到時的「重新讀取」：與精靈頁 4 同一支（重測那一台，套件內的重讀掛載的 key，M4 票 27、54）。
  const reread = useMutation({
    mutationFn: () => retestService('prowlarr', true),
    onSuccess: (next) => {
      queryClient.setQueryData(setupStatusQueryOptions.queryKey, next)
      reconnected()
    },
  })

  const frame = (children: ReactNode) => (
    <SettingsFrame title={t('settings.indexerPage.title')} lede={t('settings.indexerPage.lede')}>
      {children}
    </SettingsFrame>
  )

  // 還不知道用不用：先不畫各區，免得不用的人先看到一排紅字再收起來。讀不到健康那一份時照「在用」畫——
  // 出口（`IndexerSetAside`）與各區都還在，各區自己說讀不到。
  if (!health.isFetched)
    return frame(<p className="text-sm text-ink-dim">{t('settings.indexerPage.reading')}</p>)

  if (unused) {
    return frame(
      <IndexerUnused
        pending={usage.isPending}
        error={usage.error}
        onResume={() => usage.mutate(false)}
      />,
    )
  }

  return frame(
    <>
      <HealthSection kind="prowlarr" check={check} />
      <ServiceConnection kind="prowlarr" onConnected={reconnected} />
      {/* 區塊的 `<h2>` 讓 `IndexerActions` 裡的 `<h3>` 不跳級。 */}
      <SettingsSection id="settings-indexer-sites" title={t('settings.indexerPage.sites')}>
        {indexers.data ? (
          // `IndexerActions` 的區塊（`IndexerSites`）各自從 `mt-6` 開起，這裡收掉第一塊的外距。
          <div className="[&>:first-child]:mt-0">
            <IndexerActions
              indexers={indexers.data}
              applying={apply.isPending}
              onApply={apply.mutateAsync}
              sites={{
                onTest: testIndexers,
                onSearch: searchIndexers,
                removing: remove.isPending ? remove.variables : null,
                removeError: remove.error,
                onRemove: (id) => remove.mutate(id),
              }}
              rereading={reread.isPending}
              onReread={() => reread.mutate()}
            />
            {reread.isError && (
              <div className="mt-4">
                <RequestFailed error={reread.error} />
              </div>
            )}
          </div>
        ) : indexers.isError ? (
          <RequestFailed error={indexers.error} lead={t('indexer.stateFailed')} />
        ) : (
          // 進來只讀（M4 票 09）：這一句說的是讀清單，不是檢查。
          <p className="text-sm text-ink-dim">{t('indexer.add.loading')}</p>
        )}
      </SettingsSection>
      {indexers.data?.web_ui_login && (
        <InterfaceLoginSection
          service="prowlarr"
          current={indexers.data.web_ui_username}
          saving={login.isPending}
          onSave={async (value) => {
            const fresh = await login.mutateAsync(value)
            return {
              step: fresh.steps.find((row) => row.step === 'prowlarr_login'),
              error: fresh.error,
            }
          }}
        />
      )}
      <IndexerSetAside
        pending={usage.isPending}
        error={usage.error}
        onSetAside={() => usage.mutate(true)}
      />
    </>,
  )
}

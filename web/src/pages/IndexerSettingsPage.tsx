import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  applyIndexers,
  indexerSetupQueryOptions,
  removeIndexer,
  retestService,
  searchIndexers,
  setIndexerLogin,
  setupStatusQueryOptions,
  testIndexers,
  type IndexerSetup,
} from '../api/setup'
import { Notice } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { HealthSection } from '../settings/HealthSection'
import { InterfaceLoginSection } from '../settings/InterfaceLoginSection'
import { ServiceConnection } from '../settings/ServiceConnection'
import { useServiceCheck } from '../settings/useServiceCheck'
import { IndexerActions } from '../setup/IndexerStep'

/**
 * 設定 → Prowlarr（票 06i）。進來只讀（M4 票 09：不測任何一站）；測試、加站、試搜、移除都由人按——
 * 精靈頁 4 的那一批元件（`IndexerSites`）與同一批 `setup/indexers/*` 命令，只是沒有「之後再說」。
 * 來源、位址與 key 是另兩頁同一個連線區（`ServiceConnection`，M4 票 39：與精靈同一支
 * `POST /setup/services/prowlarr`）。套件內 Prowlarr 的介面登入是自己的一區（M4 票 07）：加站不帶
 * 登入，登入在這裡改。
 *
 * 健康卡是 Prowlarr 那一張（plan §3.2）。
 */
export function IndexerSettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const check = useServiceCheck()
  const indexers = useQuery(indexerSetupQueryOptions)

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

  return (
    <SettingsFrame title={t('settings.indexerPage.title')} lede={t('settings.indexerPage.lede')}>
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
                removeFailed: remove.isError,
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
          <Notice signal="blocked" label={t('common.failed')}>
            {t('indexer.unreachable')}
          </Notice>
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
    </SettingsFrame>
  )
}

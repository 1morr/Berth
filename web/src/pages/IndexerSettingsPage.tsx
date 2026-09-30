import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  applyIndexers,
  connectIndexer,
  indexerSetupQueryOptions,
  removeIndexer,
  searchIndexers,
  setIndexerLogin,
  testIndexers,
  type IndexerSetup,
} from '../api/setup'
import { Notice } from '../components/controls'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { HealthSection } from '../settings/HealthSection'
import { InterfaceLoginSection } from '../settings/InterfaceLoginSection'
import { useServiceCheck } from '../settings/useServiceCheck'
import { IndexerActions } from '../setup/IndexerStep'

/**
 * 設定 → 索引站（票 06i）。進來只讀（M4 票 09：不測任何一站）；測試、加站、試搜、移除、既有
 * Torznab 換網址或 key 都由人按——全部是精靈頁 4 的 `IndexerActions` 與同一批 `setup/indexers/*`
 * 命令，只是沒有「之後再說」。套件內 Prowlarr 的
 * 介面登入是自己的一區（M4 票 07）：加站不帶登入，登入在這裡改。
 *
 * 健康卡是 Prowlarr 那一張：接的是任意 Torznab 端點時，健康檢查仍以那一項報它（plan §3.2）。
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

  const apply = useMutation({ mutationFn: applyIndexers, onSuccess: absorb })
  const connect = useMutation({ mutationFn: connectIndexer, onSuccess: absorb })
  const remove = useMutation({ mutationFn: removeIndexer, onSuccess: absorb })
  const login = useMutation({ mutationFn: setIndexerLogin, onSuccess: absorb })

  return (
    <SettingsFrame title={t('settings.indexerPage.title')} lede={t('settings.indexerPage.lede')}>
      <HealthSection kind="prowlarr" check={check} />
      {/* 區塊的 `<h2>` 讓 `IndexerActions` 裡的 `<h3>` 不跳級。 */}
      <SettingsSection id="settings-indexer-sites" title={t('settings.indexerPage.sites')}>
        {indexers.data ? (
          // `IndexerActions` 的區塊各自從 `mt-6` 開起（精靈裡它們接在標題下面），這裡收掉第一塊的外距。
          <div className="[&>:first-child]:mt-0">
            <IndexerActions
              indexers={indexers.data}
              applying={apply.isPending}
              connecting={connect.isPending}
              onApply={apply.mutateAsync}
              onConnect={(input) => connect.mutate(input)}
              sites={{
                onTest: testIndexers,
                onSearch: searchIndexers,
                removing: remove.isPending ? remove.variables : null,
                removeFailed: remove.isError,
                onRemove: (id) => remove.mutate(id),
              }}
            />
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

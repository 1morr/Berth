import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  applyIndexers,
  connectIndexer,
  indexerSetupQueryOptions,
  removeIndexer,
  searchIndexers,
  type IndexerSetup,
} from '../api/setup'
import { Notice } from '../components/controls'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { HealthSection } from '../settings/HealthSection'
import { useServiceCheck } from '../settings/useServiceCheck'
import { IndexerActions } from '../setup/IndexerStep'

/**
 * 設定 → 索引站（票 06i）。加站、試搜、移除，既有 Torznab 換網址或 key——全部是精靈第 6 步的
 * `IndexerActions` 與同一批 `setup/indexers/*` 命令，只是沒有「之後再說」。
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
  const trial = useMutation({ mutationFn: searchIndexers })
  const remove = useMutation({ mutationFn: removeIndexer, onSuccess: absorb })

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
              onApply={(selected) => apply.mutate(selected)}
              onConnect={(input) => connect.mutate(input)}
              trial={{
                result: trial.data,
                searching: trial.isPending,
                failed: trial.isError,
                onSearch: (query) => trial.mutate(query),
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
          <p className="text-sm text-ink-dim">{t('health.checking')}</p>
        )}
      </SettingsSection>
    </SettingsFrame>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { ServiceKind } from '../api/schemas'
import {
  chooseService,
  choiceRefusalOf,
  retestService,
  setupStatusQueryOptions,
  type ChoiceInput,
  type SetupStatus,
} from '../api/setup'
import { RequestFailed } from '../components/RequestFailed'
import { useChoiceDraft } from '../setup/choiceDraft'
import { ServiceChoice } from '../setup/ServiceChoice'
import { SettingsSection } from './SettingsFrame'

/**
 * 一個服務的來源、位址與憑證（票 06i）。**就是精靈服務頁的頁首**（`ServiceChoice`，M4 票 15）：
 * 二選一、測試那一條、既有服務的表單都是同一個元件，送的也是同一支 `POST /setup/services/{kind}`——
 * 精靈跑完之後那一組端點只有 admin 打得到（`api/gate.py`），命令本來就冪等。
 *
 * Jellyfin 的來源鎖住（擁有者是那一台上的帳號），位址照樣改得了。存完或使用者按的重新測試之後頁面
 * 重測健康、重讀那一頁自己的資料（`onConnected`，M4 票 39：Prowlarr 的站那一區看的是測試寫下的結果）。
 */
export function ServiceConnection({
  kind,
  onConnected,
}: {
  kind: ServiceKind
  /**
   * 存下或重新測試之後。`moved` 是這一次換了一台（來源或位址變了，與後端 `choose_service` 的 `moved` 同一條）：
   * 只改帳密、原樣再存、重新測試都不是。
   */
  onConnected: (next: SetupStatus, moved: boolean) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const status = useQuery(setupStatusQueryOptions)
  const choiceDraft = useChoiceDraft()

  function absorb(next: SetupStatus) {
    queryClient.setQueryData(setupStatusQueryOptions.queryKey, next)
  }

  const choose = useMutation({
    mutationFn: (input: ChoiceInput) => chooseService(kind, input),
    onSuccess: (next) => {
      // 先比再收：`absorb` 之後快取裡就是新的那一台了。
      const moved = !sameInstance(status.data, next, kind)
      absorb(next)
      onConnected(next, moved)
    },
  })
  const retest = useMutation({
    mutationFn: (restart: boolean) => retestService(kind, restart),
    onSuccess: (next) => {
      absorb(next)
      onConnected(next, false)
    },
  })

  return (
    <SettingsSection
      id={`connection-${kind}`}
      title={t('settings.connection.title')}
      lede={t('settings.connection.lede')}
    >
      {!status.data ? (
        status.isError ? (
          <RequestFailed error={status.error} lead={t('setup.statusFailed')} />
        ) : (
          <p className="text-sm text-ink-dim">{t('health.checking')}</p>
        )
      ) : (
        <ServiceChoice
          kind={kind}
          status={status.data}
          {...choiceDraft}
          choosing={choose.isPending}
          retesting={retest.isPending}
          refusal={choiceRefusalOf(choose.error)}
          requestError={
            choose.isError && !choiceRefusalOf(choose.error)
              ? choose.error
              : retest.isError
                ? retest.error
                : null
          }
          onChoose={(input, done) => choose.mutate(input, { onSuccess: done })}
          onRetest={(restart) => retest.mutate(restart)}
          locked={kind === 'jellyfin' ? t('settings.connection.locked') : undefined}
          // Jellyfin 的來源鎖著；另兩個換來源都會清掉那一頁的結果（`_start_over`），先確認。
          switchWarning={kind === 'jellyfin' ? undefined : t(`choice.switchWarning.${kind}`)}
        />
      )}
    </SettingsSection>
  )
}

/** 前後兩份狀態裡這個服務是不是同一台：來源與位址都沒變（後端 `ServiceChoice.is_at`）。 */
function sameInstance(before: SetupStatus | undefined, after: SetupStatus, kind: ServiceKind) {
  const was = before?.services.find((row) => row.kind === kind)
  const is = after.services.find((row) => row.kind === kind)
  return (
    was !== undefined &&
    is !== undefined &&
    was.origin === is.origin &&
    was.base_url === is.base_url
  )
}

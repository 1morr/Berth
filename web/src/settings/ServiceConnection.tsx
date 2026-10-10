import { useEffect } from 'react'
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
import { WAITING_RETEST_MS } from '../setup/signals'
import { JellyfinConnection } from './JellyfinConnection'
import { SettingsSection } from './SettingsFrame'

/**
 * 一個服務的來源、位址與憑證（票 06i）。qBittorrent 與 Prowlarr **就是精靈服務頁的頁首**（`ServiceChoice`，
 * M4 票 15）：二選一、測試那一條、既有服務的表單都是同一個元件，送的也是同一支
 * `POST /setup/services/{kind}`——精靈跑完之後那一組端點只有 admin 打得到（`api/gate.py`），命令本來就冪等。
 *
 * Jellyfin 的來源換不了（擁有者是那一台上的帳號），畫的是唯讀摘要（`JellyfinConnection`，M4 票 78），
 * 既有的那一台位址照樣改得了。存完或使用者按的重新測試之後頁面重測健康、重讀那一頁自己的資料
 * （`onConnected`，M4 票 39：Prowlarr 的站那一區看的是測試寫下的結果）。
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

  // 套件內那一台還在啟動：照精靈每 3 秒重測一次（不重算時窗），直到有結論或後端判逾時（M4 票 78：
  // 這之前設定頁只畫一個不會動的倒數，配一句「每 3 秒再測一次」）。
  const waiting = status.data?.services.find((row) => row.kind === kind)?.state === 'waiting'
  const { mutate: retestNow, isPending: retesting } = retest
  useEffect(() => {
    if (!waiting || retesting || choose.isPending) return
    const timer = window.setTimeout(() => retestNow(false), WAITING_RETEST_MS)
    return () => window.clearTimeout(timer)
  }, [waiting, retesting, choose.isPending, retestNow])

  const requestError =
    choose.isError && !choiceRefusalOf(choose.error)
      ? choose.error
      : retest.isError
        ? retest.error
        : null

  return (
    <SettingsSection
      id={`connection-${kind}`}
      title={t(
        kind === 'jellyfin' ? 'settings.connection.jellyfin.title' : 'settings.connection.title',
      )}
      lede={kind === 'jellyfin' ? undefined : t('settings.connection.lede')}
    >
      {!status.data ? (
        status.isError ? (
          <RequestFailed error={status.error} lead={t('setup.statusFailed')} />
        ) : (
          <p className="text-sm text-ink-dim">{t('health.checking')}</p>
        )
      ) : kind === 'jellyfin' ? (
        <JellyfinConnection
          status={status.data}
          choosing={choose.isPending}
          retesting={retest.isPending}
          refusal={choiceRefusalOf(choose.error)}
          requestError={requestError}
          onChoose={(input, done) => choose.mutate(input, { onSuccess: done })}
          onRetest={(restart) => retest.mutate(restart)}
        />
      ) : (
        <ServiceChoice
          kind={kind}
          status={status.data}
          {...choiceDraft}
          sending={choose.isPending ? choose.variables.origin : null}
          retesting={retest.isPending}
          refusal={choiceRefusalOf(choose.error)}
          requestError={requestError}
          onChoose={(input, done) => choose.mutate(input, { onSuccess: done })}
          onRetest={(restart) => retest.mutate(restart)}
          // 換來源會清掉那一頁的結果（`_start_over`），先確認。
          switchWarning={t(`choice.switchWarning.${kind}`)}
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

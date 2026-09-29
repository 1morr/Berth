import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { ServiceKind } from '../api/schemas'
import {
  chooseService,
  retestService,
  setupStatusQueryOptions,
  type ChoiceInput,
  type SetupStatus,
} from '../api/setup'
import { Notice } from '../components/controls'
import { useChoiceDraft } from '../setup/choiceDraft'
import { ServiceChoice } from '../setup/ServiceChoice'
import { SettingsSection } from './SettingsFrame'

/**
 * 一個服務的來源、位址與憑證（票 06i）。**就是精靈服務頁的頁首**（`ServiceChoice`，M4 票 15）：
 * 二選一、測試那一條、既有服務的表單都是同一個元件，送的也是同一支 `POST /setup/services/{kind}`——
 * 精靈跑完之後那一組端點只有 admin 打得到（`api/gate.py`），命令本來就冪等。
 *
 * Jellyfin 的來源鎖住（擁有者是那一台上的帳號），位址照樣改得了。存完之後頁面重測健康
 * （`onConnected`），結果就在上面那張卡上。
 */
export function ServiceConnection({
  kind,
  onConnected,
}: {
  kind: ServiceKind
  onConnected: () => void
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
      absorb(next)
      onConnected()
    },
  })
  const retest = useMutation({
    mutationFn: (restart: boolean) => retestService(kind, restart),
    onSuccess: absorb,
  })

  return (
    <SettingsSection
      id={`connection-${kind}`}
      title={t('settings.connection.title')}
      lede={t('settings.connection.lede')}
    >
      {!status.data ? (
        <p className="text-sm text-ink-dim">
          {status.isError ? t('setup.statusFailed') : t('health.checking')}
        </p>
      ) : (
        <ServiceChoice
          kind={kind}
          status={status.data}
          {...choiceDraft}
          choosing={choose.isPending}
          retesting={retest.isPending}
          onChoose={(input, settled) => choose.mutate(input, { onSettled: settled })}
          onRetest={(restart) => retest.mutate(restart)}
          locked={kind === 'jellyfin' ? t('settings.connection.locked') : undefined}
          switchWarning={kind === 'qbittorrent' ? t('choice.switchWarning.qbittorrent') : undefined}
        />
      )}
      {(choose.isError || retest.isError) && (
        <div className="mt-3">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.connection.failed')}
          </Notice>
        </div>
      )}
    </SettingsSection>
  )
}

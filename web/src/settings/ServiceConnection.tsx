import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { ServiceKind } from '../api/schemas'
import {
  connectService,
  detectServices,
  setupStatusQueryOptions,
  type ConnectInput,
  type SetupStatus,
} from '../api/setup'
import { Notice } from '../components/controls'
import { MooringLine } from '../setup/MooringLine'
import { needsConnectionForm, probeEndpoint } from '../setup/signals'
import { SettingsSection } from './SettingsFrame'

/**
 * 一個服務的位址與憑證（票 06i）。**就是精靈第 2 步的那一條纜繩**（`MooringLine`）：
 * 判定、連線表單、手動步驟都是同一個元件，送的也是同一支 `POST /setup/services/{kind}`——
 * 精靈跑完之後那一組端點只有 admin 打得到（`api/gate.py`），命令本來就冪等。
 *
 * 表單只給既有服務，與精靈同一條規則（`needsConnectionForm`）：套件內的位址是 compose 決定的、
 * 憑證是 Berth 自己寫進去的，這裡沒有要填的東西。存完之後頁面重測健康（`onConnected`），
 * 結果就在上面那張卡上。
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
  const detection = status.data?.services.find((row) => row.kind === kind)

  function absorb(next: SetupStatus) {
    queryClient.setQueryData(setupStatusQueryOptions.queryKey, next)
  }

  const connect = useMutation({
    mutationFn: (input: ConnectInput) => connectService(kind, input),
    onSuccess: (next) => {
      absorb(next)
      onConnected()
    },
  })
  const redetect = useMutation({
    mutationFn: () => detectServices(false, kind),
    onSuccess: absorb,
  })

  return (
    <SettingsSection
      id={`connection-${kind}`}
      title={t('settings.connection.title')}
      lede={detection && needsConnectionForm(detection) ? t('settings.connection.lede') : undefined}
    >
      {!status.data ? (
        <p className="text-sm text-ink-dim">
          {status.isError ? t('detect.failed') : t('health.checking')}
        </p>
      ) : !detection ? (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('detect.failed')}
        </Notice>
      ) : needsConnectionForm(detection) ? (
        <ul className="grid">
          <MooringLine
            kind={kind}
            endpoint={probeEndpoint(status.data, kind)}
            detection={detection}
            tying={false}
            waitedSeconds={status.data.waited_seconds}
            windowSeconds={status.data.window_seconds}
            connecting={connect.isPending}
            redetecting={redetect.isPending}
            onConnect={(_, input) => connect.mutate(input)}
            onRedetect={() => redetect.mutate()}
          />
        </ul>
      ) : (
        <p className="max-w-prose text-sm text-ink-dim">{t('settings.connection.bundled')}</p>
      )}
      {connect.isError && (
        <div className="mt-3">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('settings.connection.failed')}
          </Notice>
        </div>
      )}
    </SettingsSection>
  )
}

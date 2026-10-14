import { useTranslation } from 'react-i18next'

import type { ServiceKind } from '../api/schemas'
import type { ComposeHosts, SetupStatus } from '../api/setup'
import { CopyLine } from '../components/controls'
import { SERVICE_LABEL } from '../components/services'
import { formatList } from '../i18n/list'
import { composeProfiles } from './signals'

/**
 * 選了既有的服務，套件內那一台閒著（審計 P2-20）：停掉它的兩行只在這裡給（M4 票 103）。選的那一頁各給一次時
 * `COMPOSE_PROFILES` 一頁比一頁短，三份說法不同；那幾頁現在只指到這一段。不叫「Unused」：CONTEXT.md 的
 * **Unused service** 是管理員選了不用的服務（不用 Prowlarr），這裡說的是選了既有之後還開著的套件內容器。
 *
 * 只列套件內那一台還解得到主機名的（`composeHosts`，M4 票 30）：已經停掉或不在 `COMPOSE_PROFILES` 裡的不再叫人
 * 停。沒問到的照列——多說一次無害，漏說了容器就一直開著。
 */
export function IdleBundled({
  status,
  composeHosts = {},
}: {
  status: SetupStatus
  composeHosts?: ComposeHosts
}) {
  const { t, i18n } = useTranslation()
  const kinds: ServiceKind[] = status.services
    .filter((row) => row.origin === 'existing' && composeHosts[row.kind] !== false)
    .map((row) => row.kind)
  const [first] = kinds
  if (first === undefined) return null
  // 照整份選擇算：選了既有的都已經拿掉（`composeProfiles`）。三個都選既有時是空的一行。
  const profiles = composeProfiles(status, first, 'existing')

  return (
    <section aria-labelledby="idle-bundled" className="mt-6 grid gap-3">
      <h3 id="idle-bundled" className="label text-ink-dim">
        {t('complete.idle.title')}
      </h3>
      <p className="max-w-prose text-xs text-ink-dim">
        {t('complete.idle.body', {
          services: formatList(
            kinds.map((kind) => t(SERVICE_LABEL[kind])),
            i18n.language,
          ),
        })}
        {profiles === 'COMPOSE_PROFILES=' && ` ${t('complete.idle.onlyBerth')}`}
      </p>
      <div className="grid gap-px">
        <CopyLine command={profiles} />
        <CopyLine command={`docker compose stop ${kinds.join(' ')}`} />
      </div>
    </section>
  )
}

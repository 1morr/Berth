import { useTranslation } from 'react-i18next'

import { CopyLine } from './controls'
import { hostSource, mountSnippet, runMount, type ExistingMount } from './routeChecks'

/**
 * Unraid 模板「Add another Path, Port, Variable, Label or Device」那一格的欄位（Unraid 7.1.4
 * `dynamix.docker.manager` 的介面字串，`docs/research/unraid-trial-2026-10-08.md` §6 U6）。產品介面的字，
 * 不翻譯。
 */
const UNRAID_FIELDS = {
  configType: 'Config Type',
  name: 'Name',
  containerPath: 'Container Path',
  hostPath: 'Host Path',
  accessMode: 'Access Mode',
} as const

/**
 * 使用者自己的那一台要多加的那一條掛載（M4 票 36、63，審計 P1-6）：compose、`docker run`、Unraid 模板三種
 * 寫法，都帶著 Berth 的 `DATA_ROOT` 真正的值——原本是 `${DATA_ROOT}`，要人自己去 Berth 的 `.env` 找。
 *
 * 值是相對路徑時說它相對於哪裡、要換成絕對路徑：原樣貼進另一份 compose 會指到另一個資料夾。不知道值
 * （compose 沒傳進來）時片段照舊是 `${DATA_ROOT}`，說去哪裡找。Unraid 那一種收起來：只有用模板的人要看。
 */
export function MountFix({ service, root, host }: ExistingMount) {
  const { t } = useTranslation()
  const source = hostSource(host)
  const note = !host.path
    ? t('routes.fix.mount.hostUnknown')
    : host.relative
      ? t('routes.fix.mount.hostRelative', { path: host.path })
      : null

  return (
    <div className="grid min-w-0 gap-2" data-testid="mount-fix">
      {note && (
        <p className="max-w-prose border-l-2 border-assigned pl-2 text-xs text-ink">{note}</p>
      )}
      <div className="grid grid-cols-1 gap-px">
        <CopyLine command={mountSnippet(service, root, source)} />
        <CopyLine command={runMount(root, source)} />
      </div>
      <details className="min-w-0">
        <summary className="label cursor-pointer text-ink-dim hover:text-ink">
          {t('routes.fix.mount.unraid')}
        </summary>
        <div className="mt-2 grid gap-2 border-2 border-rule bg-hull px-3 py-3">
          <p className="max-w-prose text-xs text-ink-dim">{t('routes.fix.mount.unraidSteps')}</p>
          <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-xs">
            <UnraidField label={UNRAID_FIELDS.configType} value="Path" />
            <UnraidField label={UNRAID_FIELDS.name} value="Berth" />
            <UnraidField label={UNRAID_FIELDS.containerPath} value={root} />
            <UnraidField label={UNRAID_FIELDS.hostPath} value={source} />
            <UnraidField label={UNRAID_FIELDS.accessMode} value="Read/Write" />
          </dl>
          <p className="max-w-prose text-xs text-ink-dim">
            {t('routes.fix.mount.unraidNested', { root })}
          </p>
        </div>
      </details>
    </div>
  )
}

function UnraidField({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="label self-center text-ink-dim">{label}</dt>
      <dd className="value wrap-anywhere text-ink">{value}</dd>
    </>
  )
}

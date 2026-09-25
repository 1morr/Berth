import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import type { ConnectInput, ServiceDetection } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { CopyLine, Field, GhostButton, PasswordField } from '../components/controls'
import { ORIGIN_LABEL, SERVICE_LABEL, detailLabel } from '../components/services'
import { SIGNAL_FILL } from '../components/signal'
import {
  EXAMPLE_ADDRESS,
  REASON_LABEL,
  connectFields,
  needsConnectionForm,
  signalOf,
} from './signals'

/**
 * 一條纜繩：一個服務的探測結果。繫上就把實際結果數值留在旁邊；失敗變紅並**就地**展開
 * 可複製的手動步驟與連線表單，不跳離當前泊位（direction contract 的署名互動）。
 */
export function MooringLine({
  kind,
  endpoint,
  detection,
  tying,
  waitedSeconds,
  windowSeconds,
  connecting,
  redetecting,
  onConnect,
  onRedetect,
}: {
  kind: ServiceKind
  /** 探哪裡（`probeEndpoint`）。 */
  endpoint: string
  detection: ServiceDetection | undefined
  /** 還在探測（或還沒輪到這一條繫上）。 */
  tying: boolean
  /** 本輪已等待的秒數與上限，只有還在等的那一條用得到。 */
  waitedSeconds: number
  windowSeconds: number
  connecting: boolean
  /** 這一條正在重新偵測（`onRedetect` 送出去還沒回來）。 */
  redetecting: boolean
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
  /** 只重新探這一個服務（票 06d）。全部重新探測留在第 2 步的主要動作上。 */
  onRedetect: (kind: ServiceKind) => void
}) {
  const { t } = useTranslation()
  const signal = tying ? 'working' : signalOf(detection)
  const showForm = !tying && needsConnectionForm(detection)
  // 還沒解決的那一條才給：逾時、探不到、要帳密。還在探的由輪詢接手，不必人按。
  const redetectable =
    !tying && detection !== undefined && !detection.resolved && detection.origin !== 'pending'

  return (
    <li className={`min-w-0 border-2 ${showForm ? 'border-rule-strong' : 'border-rule'} bg-well`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[signal]}`}>
          {tying
            ? t('detect.running')
            : detection
              ? t(ORIGIN_LABEL[detection.origin])
              : t('detect.empty')}
        </span>
        <span className="value text-sm font-semibold text-ink">{t(SERVICE_LABEL[kind])}</span>
        <span className="value ml-auto min-w-0 truncate text-xs text-ink-dim">{endpoint}</span>
      </div>

      {!tying && detection && (
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 border-t-2 border-rule px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <dt className="label self-center text-ink-dim">{t('detect.cutaway.verdict')}</dt>
          <dd className="text-sm text-ink">{t(REASON_LABEL[detection.reason])}</dd>
          {detection.detail && (
            <>
              <dt className="label mt-1 self-center text-ink-dim">{t(detailLabel(kind))}</dt>
              <dd className="value mt-1 text-sm text-ink">{detection.detail}</dd>
            </>
          )}
          {detection.origin === 'pending' && (
            <>
              {/* 倒數貼在還在等的那一條上，不放在清單底下——它說的就是這個服務。 */}
              <dt className="label mt-1 self-center text-ink-dim">{t('detect.waitingLabel')}</dt>
              <dd className="mt-1 text-sm text-ink">
                <span className="value">
                  {t('detect.waiting', { waited: waitedSeconds, window: windowSeconds })}
                </span>
                <span className="mt-1 block text-xs text-ink-dim">{t('detect.waitingHint')}</span>
              </dd>
            </>
          )}
        </dl>
      )}

      {redetectable && (
        <div className="border-t-2 border-rule px-4 py-3">
          <RedetectButton kind={kind} busy={redetecting} onRedetect={onRedetect} />
        </div>
      )}

      {showForm && detection && (
        <ConnectPanel
          kind={kind}
          detection={detection}
          connecting={connecting}
          onConnect={onConnect}
        />
      )}
    </li>
  )
}

/**
 * 重新偵測這一個服務（票 06d）：放在出問題的那一格旁邊，不是每頁頂部。啟動中的暫時錯誤由
 * 輪詢接手（06g），這顆鍵是給「使用者自己改了東西之後」——改了 `COMPOSE_PROFILES`、port、
 * 把容器叫起來。泊位頁連不上的時候也用同一顆。
 */
export function RedetectButton({
  kind,
  busy,
  onRedetect,
}: {
  kind: ServiceKind
  busy: boolean
  onRedetect: (kind: ServiceKind) => void
}) {
  const { t } = useTranslation()

  return (
    <GhostButton type="button" busy={busy} onClick={() => onRedetect(kind)}>
      {busy ? t('detect.redetecting') : t('detect.redetect', { service: t(SERVICE_LABEL[kind]) })}
    </GhostButton>
  )
}

function ConnectPanel({
  kind,
  detection,
  connecting,
  onConnect,
}: {
  kind: ServiceKind
  detection: ServiceDetection
  connecting: boolean
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
}) {
  const { t } = useTranslation()
  const [baseUrl, setBaseUrl] = useState(detection.base_url)
  const [apiKey, setApiKey] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const fields = connectFields(kind)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!baseUrl.trim()) return
    onConnect(kind, {
      base_url: baseUrl.trim(),
      api_key: apiKey.trim(),
      username,
      password,
    })
  }

  return (
    <div className="border-t-2 border-rule bg-hull px-4 py-4">
      <h3 className="text-sm font-semibold text-ink">
        {t('connect.title', { service: t(SERVICE_LABEL[kind]) })}
      </h3>
      <p className="mt-1 max-w-prose text-xs text-ink-dim">{t(`connect.hint.${kind}`)}</p>

      <form onSubmit={submit} noValidate className="mt-4 grid gap-4">
        <Field
          label={t('connect.field.baseUrl')}
          value={baseUrl}
          inputMode="url"
          placeholder={EXAMPLE_ADDRESS[kind]}
          onChange={(event) => setBaseUrl(event.target.value)}
        />
        {fields.includes('apiKey') && (
          <PasswordField
            label={t('connect.field.apiKey')}
            value={apiKey}
            autoComplete="off"
            onChange={(event) => setApiKey(event.target.value)}
          />
        )}
        {fields.includes('credentials') && (
          <>
            <Field
              label={t('connect.field.username')}
              value={username}
              autoComplete="off"
              onChange={(event) => setUsername(event.target.value)}
            />
            <PasswordField
              label={t('connect.field.password')}
              value={password}
              autoComplete="off"
              onChange={(event) => setPassword(event.target.value)}
            />
          </>
        )}
        <div>
          <GhostButton type="submit" busy={connecting}>
            {connecting ? t('connect.submitting') : t('connect.submit')}
          </GhostButton>
        </div>
      </form>

      <ManualSteps kind={kind} detection={detection} />
    </div>
  )
}

function ManualSteps({ kind, detection }: { kind: ServiceKind; detection: ServiceDetection }) {
  const { t } = useTranslation()
  const service = t(SERVICE_LABEL[kind])

  if (detection.reason === 'not_deployed') {
    return (
      <section className="mt-5 border-t-2 border-rule pt-4">
        <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
        <p className="mt-2 max-w-prose text-xs text-ink-dim">
          {t('connect.fix.notDeployed', { service })}
        </p>
        <div className="mt-2">
          <CopyLine command={`COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr`} />
        </div>
      </section>
    )
  }

  if (detection.origin === 'timeout' || detection.reason === 'unreachable') {
    return (
      <section className="mt-5 border-t-2 border-rule pt-4">
        <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
        <p className="mt-2 max-w-prose text-xs text-ink-dim">{t('connect.fix.unreachable')}</p>
        <div className="mt-2 grid grid-cols-1 gap-px">
          <CopyLine command={`docker compose ps ${kind}`} />
          <CopyLine command={`docker compose logs --tail 50 ${kind}`} />
        </div>
      </section>
    )
  }

  return null
}

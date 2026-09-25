import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { type ConnectInput, type SetupStatus } from '../api/setup'
import { SERVICE_KINDS, type ServiceKind } from '../api/schemas'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { MooringLine } from './MooringLine'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { probeEndpoint } from './signals'
import { StepFrame } from './StepFrame'

/** 逐條纜繩繫上的節拍。整份結果是一次回來的，這裡只是揭露的節奏。 */
const REVEAL_STEP_MS = 140

/**
 * 第 2 步：偵測服務（plan §9.3）。
 *
 * 按下靠泊後那一格不是換成 spinner，而是逐條纜繩繫上，每完成一項把實際結果數值留在旁邊；
 * 任一條失敗變紅並就地展開手動步驟，其餘已繫上的纜繩不動（direction contract）。
 */
export function DetectStep({
  status,
  probing,
  connectingKind,
  redetectingKind,
  failed,
  onDetect,
  onConnect,
  onRedetect,
  onContinue,
  nav,
}: {
  status: SetupStatus
  probing: boolean
  connectingKind: ServiceKind | null
  /** 只重探一個服務時是哪一個（票 06d）。 */
  redetectingKind: ServiceKind | null
  failed: boolean
  onDetect: (restart: boolean) => void
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
  onRedetect: (kind: ServiceKind) => void
  /** 前往泊位 1。判定全部出來了才有，而且是使用者自己按（票 06d：停在結果上）。 */
  onContinue: () => void
  /** 上一個泊位（`BerthNav`）。 */
  nav: ReactNode
}) {
  const { t } = useTranslation()
  const byKind = new Map(status.services.map((row) => [row.kind, row]))
  const probed = status.services.length > 0
  const timedOut = status.services.some((row) => row.origin === 'timeout')
  // 每個服務都連得上了才走得下去；沒解決的那幾個要使用者先補連線資訊（plan §9.3 第 2 步）。
  const resolved = probed && status.services.every((row) => row.resolved)
  // 換一輪結果就換 key：重新掛載讓揭露從第一條纜繩重來，不必在 effect 裡回寫 state。
  const revealKey = probing
    ? 'probing'
    : status.services.map((row) => `${row.kind}:${row.origin}:${row.reason}`).join('|')

  return (
    <StepFrame
      cutaway={
        <Cutaway title={t('detect.cutaway.title')}>
          {SERVICE_KINDS.map((kind) => (
            <CutawayRow
              key={kind}
              code
              term={probeEndpoint(status, kind)}
              value={t(`detect.cutaway.${kind}`)}
            />
          ))}
        </Cutaway>
      }
    >
      <h2 className="text-lg font-semibold text-ink">{t('detect.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('detect.lede')}</p>

      {/* live region 在換 key 重掛的那一層外面（票 06h 的 audit）：每一輪結果換一份新的清單，
          掛在清單上的 aria-live 會跟著新內容一起出現，那一輪就不會被念出來。 */}
      <div aria-live="polite" aria-busy={probing}>
        <MooringSequence
          key={revealKey}
          probing={probing}
          probed={probed}
          byKind={byKind}
          endpointOf={(kind) => probeEndpoint(status, kind)}
          waitedSeconds={status.waited_seconds}
          windowSeconds={status.window_seconds}
          connectingKind={connectingKind}
          redetectingKind={redetectingKind}
          onConnect={onConnect}
          onRedetect={onRedetect}
        />
      </div>

      {failed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('detect.failed')}
          </Notice>
        </div>
      )}

      <div className={`mt-6 ${STICKY_ACTION}`}>
        {!probed ? (
          <PrimaryButton type="button" busy={probing} onClick={() => onDetect(false)}>
            {probing ? t('detect.running') : t('detect.run')}
          </PrimaryButton>
        ) : resolved ? (
          // 判定全部出來了才前進，而且是使用者自己按——不然他根本看不到逐條纜繩的結果。
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,18rem)_auto] sm:items-center">
            // 探測做完、「開始探測」換掉之後，焦點接到這一顆（`StepFrame`，票 06h）。
            <PrimaryButton type="button" busy={probing} data-berth-next onClick={onContinue}>
              {t('detect.continue')}
            </PrimaryButton>
            <GhostButton type="button" busy={probing} onClick={() => onDetect(false)}>
              {probing ? t('detect.running') : t('detect.rerun')}
            </GhostButton>
          </div>
        ) : timedOut ? (
          <PrimaryButton type="button" busy={probing} onClick={() => onDetect(true)}>
            {probing ? t('detect.running') : t('detect.retry')}
          </PrimaryButton>
        ) : (
          <GhostButton type="button" busy={probing} onClick={() => onDetect(false)}>
            {probing ? t('detect.running') : t('detect.rerun')}
          </GhostButton>
        )}
      </div>
      {nav}
    </StepFrame>
  )
}

/**
 * 靠泊序列：逐條纜繩繫上。整份結果是一次回來的，這裡只排它們出現的順序，
 * 顯示的值全部是實測的；`prefers-reduced-motion` 時一次全出。
 */
function MooringSequence({
  probing,
  probed,
  byKind,
  endpointOf,
  waitedSeconds,
  windowSeconds,
  connectingKind,
  redetectingKind,
  onConnect,
  onRedetect,
}: {
  probing: boolean
  probed: boolean
  byKind: Map<ServiceKind, SetupStatus['services'][number]>
  endpointOf: (kind: ServiceKind) => string
  waitedSeconds: number
  windowSeconds: number
  connectingKind: ServiceKind | null
  redetectingKind: ServiceKind | null
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
  onRedetect: (kind: ServiceKind) => void
}) {
  const total = SERVICE_KINDS.length
  const [revealed, setRevealed] = useState(() => (prefersReducedMotion() ? total : 0))

  useEffect(() => {
    if (probing || !probed || prefersReducedMotion()) return
    const timers = Array.from({ length: total }, (_, index) =>
      window.setTimeout(() => setRevealed(index + 1), REVEAL_STEP_MS * (index + 1)),
    )
    return () => timers.forEach(window.clearTimeout)
  }, [probing, probed, total])

  return (
    <ol className="mt-6 grid gap-3" data-testid="mooring-sequence">
      {SERVICE_KINDS.map((kind, index) => (
        <MooringLine
          key={kind}
          kind={kind}
          endpoint={endpointOf(kind)}
          detection={probed ? byKind.get(kind) : undefined}
          tying={probing || (probed && index >= revealed)}
          waitedSeconds={waitedSeconds}
          windowSeconds={windowSeconds}
          connecting={connectingKind === kind}
          redetecting={redetectingKind === kind}
          onConnect={onConnect}
          onRedetect={onRedetect}
        />
      ))}
    </ol>
  )
}

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

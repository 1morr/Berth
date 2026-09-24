import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { type ConnectInput, type SetupStatus } from '../api/setup'
import { SERVICE_KINDS, type ServiceKind } from '../api/schemas'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { MooringLine } from './MooringLine'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { PROBE_ENDPOINT } from './signals'

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
  failed,
  onDetect,
  onConnect,
  onContinue,
}: {
  status: SetupStatus
  probing: boolean
  connectingKind: ServiceKind | null
  failed: boolean
  onDetect: (restart: boolean) => void
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
  onContinue: () => void
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
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          <Cutaway title={t('detect.cutaway.title')}>
            {SERVICE_KINDS.map((kind) => (
              <CutawayRow
                key={kind}
                code
                term={PROBE_ENDPOINT[kind]}
                value={t(`detect.cutaway.${kind}`)}
              />
            ))}
          </Cutaway>
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">{t('detect.title')}</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('detect.lede')}</p>

        <MooringSequence
          key={revealKey}
          probing={probing}
          probed={probed}
          byKind={byKind}
          waitedSeconds={status.waited_seconds}
          windowSeconds={status.window_seconds}
          connectingKind={connectingKind}
          onConnect={onConnect}
        />

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
              <PrimaryButton type="button" busy={probing} onClick={onContinue}>
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
      </div>
    </div>
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
  waitedSeconds,
  windowSeconds,
  connectingKind,
  onConnect,
}: {
  probing: boolean
  probed: boolean
  byKind: Map<ServiceKind, SetupStatus['services'][number]>
  waitedSeconds: number
  windowSeconds: number
  connectingKind: ServiceKind | null
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
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
    <ol
      aria-live="polite"
      aria-busy={probing}
      className="mt-6 grid gap-3"
      data-testid="mooring-sequence"
    >
      {SERVICE_KINDS.map((kind, index) => (
        <MooringLine
          key={kind}
          kind={kind}
          detection={probed ? byKind.get(kind) : undefined}
          tying={probing || (probed && index >= revealed)}
          waitedSeconds={waitedSeconds}
          windowSeconds={windowSeconds}
          connecting={connectingKind === kind}
          onConnect={onConnect}
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

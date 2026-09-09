import { useTranslation } from 'react-i18next'

import { JELLYFIN_STEPS, type JellyfinConnectInput, type JellyfinSetup } from '../api/setup'
import { type SetupStep } from '../api/schemas'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { JellyfinExisting } from './JellyfinExisting'
import { StepLine } from '../components/StepLine'
import { isSettled } from '../components/steps'
import { STEP_ENDPOINT, STEP_FIX, STEP_LABEL, isJellyfinStep, manualSteps } from './jellyfinSteps'

/**
 * 泊位 1：Jellyfin（plan §9.3 第 3 步）。兩條路徑由第 2 步的判定決定，使用者不必自己選。
 *
 * 套件內：一顆按鈕跑完 plan §9.4 的九步，畫面逐條纜繩顯示結果與實測值。
 * 既有：連線表單 + 媒體庫清單 + 兩顆要二次確認的按鈕（`JellyfinExisting`）。
 */
export function JellyfinStep({
  setup,
  running,
  bootstrapFailed,
  signInFailed,
  onBootstrap,
  onConnect,
  onAddPath,
  onInstallPlugin,
  connecting,
  addingPath,
  installing,
}: {
  setup: JellyfinSetup
  running: boolean
  /** 請求本身沒跑完（後端沒回應）。步驟自己的失敗在 `setup.steps` 裡，各自貼在它那一行。 */
  bootstrapFailed: boolean
  signInFailed: boolean
  onBootstrap: () => void
  onConnect: (input: JellyfinConnectInput) => void
  onAddPath: (library: string) => void
  onInstallPlugin: () => void
  connecting: boolean
  addingPath: string | null
  installing: boolean
}) {
  const { t } = useTranslation()
  const bundled = setup.origin === 'bundled'

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          {bundled ? <SequenceCutaway /> : <ServerCutaway setup={setup} />}
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">
          {t(bundled ? 'jellyfin.bundled.title' : 'jellyfin.existing.title')}
        </h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">
          {t(bundled ? 'jellyfin.bundled.lede' : 'jellyfin.existing.lede')}
        </p>

        {bundled ? (
          <BootstrapSequence
            setup={setup}
            running={running}
            failed={bootstrapFailed}
            onBootstrap={onBootstrap}
          />
        ) : (
          <JellyfinExisting
            setup={setup}
            signInFailed={signInFailed}
            connecting={connecting}
            addingPath={addingPath}
            installing={installing}
            onConnect={onConnect}
            onAddPath={onAddPath}
            onInstallPlugin={onInstallPlugin}
          />
        )}
      </div>
    </div>
  )
}

/** 剖面即預覽：九步各自打哪一支端點，按之前就攤開來（direction contract 的 Proof）。 */
function SequenceCutaway() {
  const { t } = useTranslation()

  return (
    <Cutaway title={t('jellyfin.cutaway.sequence')}>
      {JELLYFIN_STEPS.map((step) => (
        <CutawayRow key={step} code term={STEP_ENDPOINT[step]} value={t(STEP_LABEL[step])} />
      ))}
    </Cutaway>
  )
}

/** 既有服務的剖面：這台伺服器現在是什麼樣子，全部是它自己報出來的值。 */
function ServerCutaway({ setup }: { setup: JellyfinSetup }) {
  const { t } = useTranslation()
  const version = setup.steps.find((row) => row.step === 'public_info')?.detail

  return (
    <Cutaway title={t('jellyfin.cutaway.server')}>
      <CutawayRow term={t('connect.field.baseUrl')} value={setup.base_url || '—'} />
      <CutawayRow term={t('detail.version')} value={version || '—'} muted={!version} />
      <CutawayRow
        term={t('jellyfin.cutaway.apiKey')}
        value={t(setup.api_key_present ? 'jellyfin.cutaway.held' : 'jellyfin.cutaway.absent')}
        muted={!setup.api_key_present}
      />
      <CutawayRow
        term={t('jellyfin.cutaway.libraries')}
        value={setup.libraries.length ? String(setup.libraries.length) : '—'}
        muted={setup.libraries.length === 0}
      />
      <CutawayRow
        term={t('jellyfin.cutaway.mergeVersions')}
        value={t(
          setup.merge_versions_installed
            ? 'jellyfin.cutaway.installed'
            : 'jellyfin.cutaway.notInstalled',
        )}
        muted={!setup.merge_versions_installed}
      />
    </Cutaway>
  )
}

/**
 * 靠泊序列：九條纜繩。整份結果在請求回來時一次到位，但每一步在後端做之前就把自己標成
 * `running` 並存下來，所以請求還在飛的時候前端輪詢就看得到序列走到哪裡。
 */
function BootstrapSequence({
  setup,
  running,
  failed,
  onBootstrap,
}: {
  setup: JellyfinSetup
  running: boolean
  failed: boolean
  onBootstrap: () => void
}) {
  const { t } = useTranslation()
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  const started = setup.steps.length > 0
  const broke = setup.steps.find((row) => row.status === 'failed')
  const done = started && !running && setup.steps.every((row) => isSettled(row.status))

  return (
    <>
      <ol aria-live="polite" aria-busy={running} className="mt-6 grid gap-3" data-testid="sequence">
        {JELLYFIN_STEPS.map((step) => (
          <JellyfinLine
            key={step}
            step={step}
            row={byStep.get(step)}
            baseUrl={setup.base_url}
            running={running}
          />
        ))}
      </ol>

      {done && (
        <div className="mt-4">
          <Notice signal="secured" label={t('status.ok')}>
            {t('jellyfin.bundled.done')}
          </Notice>
        </div>
      )}

      {failed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('jellyfin.bundled.requestFailed')}
          </Notice>
        </div>
      )}

      <div className={`mt-6 ${STICKY_ACTION}`}>
        {done ? (
          <GhostButton type="button" disabled={running} onClick={onBootstrap}>
            {t('jellyfin.bundled.rerun')}
          </GhostButton>
        ) : (
          <PrimaryButton type="button" disabled={running} onClick={onBootstrap}>
            {running
              ? t('jellyfin.bundled.running')
              : t(broke ? 'jellyfin.bundled.retry' : 'jellyfin.bundled.run')}
          </PrimaryButton>
        )}
      </div>
    </>
  )
}

/** 一條纜繩：plan §9.4 的一個步驟。手動步驟要在**他自己那台** Jellyfin 上做。 */
function JellyfinLine({
  step,
  row,
  baseUrl,
  running,
}: {
  step: string
  row: SetupStep | undefined
  baseUrl: string
  running: boolean
}) {
  const { t } = useTranslation()
  const known = isJellyfinStep(step)

  return (
    <StepLine
      label={known ? t(STEP_LABEL[step]) : step}
      endpoint={known ? STEP_ENDPOINT[step] : ''}
      row={row}
      fix={known ? t(STEP_FIX[step]) : t('jellyfin.fix.generic')}
      commands={manualSteps(step, baseUrl)}
    >
      {!running && <p className="mt-3 text-xs text-ink-dim">{t('jellyfin.fix.retryHint')}</p>}
    </StepLine>
  )
}

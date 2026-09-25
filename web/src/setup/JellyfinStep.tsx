import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import {
  JELLYFIN_STEPS,
  type JellyfinConnectInput,
  type JellyfinSetup,
  type LibraryDraft,
} from '../api/setup'
import { type SetupStep } from '../api/schemas'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { BundledLibraries } from './BundledLibraries'
import { JellyfinExisting } from './JellyfinExisting'
import { useLibraryDraft, type LibraryDraftState } from './useLibraryDraft'
import { StepLine } from '../components/StepLine'
import { isSettled } from '../components/steps'
import { STEP_ENDPOINT, STEP_FIX, STEP_LABEL, isJellyfinStep, manualSteps } from './jellyfinSteps'

/**
 * 泊位 1：Jellyfin（plan §9.3 第 3 步）。兩條路徑由第 2 步的判定決定，使用者不必自己選。
 *
 * 套件內：剖面是一張要建的媒體庫清單（票 06f），一顆按鈕跑完 plan §9.4 的七步，畫面逐條纜繩
 * 顯示結果與實測值。
 * 既有：連線表單 + 媒體庫清單 + 一顆要二次確認的按鈕（`JellyfinExisting` 的「加入 Berth 路徑」）。
 */
export function JellyfinStep({
  setup,
  running,
  bootstrapFailed,
  signInFailed,
  onBootstrap,
  onSaveLibraries,
  savingLibraries,
  saveLibrariesFailed,
  onConnect,
  onAddPath,
  connecting,
  addingPath,
  note,
  nav,
  redetect,
}: {
  setup: JellyfinSetup
  running: boolean
  /** 請求本身沒跑完（後端沒回應）。步驟自己的失敗在 `setup.steps` 裡，各自貼在它那一行。 */
  bootstrapFailed: boolean
  signInFailed: boolean
  /** 帶著剖面上的清單：先存它，再跑序列（`bootstrap` 讀的是存下來的那一份）。 */
  onBootstrap: (libraries: LibraryDraft[]) => void
  /** 剖面停手一會兒就存（票 06f）。 */
  onSaveLibraries: (libraries: LibraryDraft[]) => void
  savingLibraries: boolean
  /** 清單存不下來的那一句，沒有就是 `null`。 */
  saveLibrariesFailed: string | null
  onConnect: (input: JellyfinConnectInput) => void
  onAddPath: (library: string) => void
  connecting: boolean
  addingPath: string | null
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
  /** 請求沒走完（多半是連不上）時的「重新偵測這個服務」（票 06d）。 */
  redetect?: ReactNode
}) {
  const { t } = useTranslation()
  const bundled = setup.origin === 'bundled'
  // 既有路徑用不到它，但 hook 不能有條件地呼叫；它只在清單真的被改過時才存。
  const draft = useLibraryDraft(setup, onSaveLibraries)

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 bg-hull p-6">
        <div className="lg:sticky lg:top-6">
          {bundled ? (
            <div className="grid gap-6">
              <BundledLibraries
                draft={draft}
                libraryRoot={setup.library_root}
                locked={running}
                saving={savingLibraries}
                saveFailed={saveLibrariesFailed}
              />
              <SequenceCutaway />
            </div>
          ) : (
            <ServerCutaway setup={setup} />
          )}
        </div>
      </div>

      <div className="min-w-0 bg-hull p-6">
        <h2 className="text-lg font-semibold text-ink">
          {t(bundled ? 'jellyfin.bundled.title' : 'jellyfin.existing.title')}
        </h2>
        <p className="mt-2 max-w-prose text-sm text-ink-dim">
          {t(bundled ? 'jellyfin.bundled.lede' : 'jellyfin.existing.lede')}
        </p>
        {note}

        {!setup.version_supported && <VersionNotice version={setup.version} />}

        {bundled ? (
          <BootstrapSequence
            setup={setup}
            draft={draft}
            running={running}
            failed={bootstrapFailed}
            onBootstrap={onBootstrap}
            redetect={redetect}
          />
        ) : (
          <JellyfinExisting
            setup={setup}
            signInFailed={signInFailed}
            connecting={connecting}
            addingPath={addingPath}
            onConnect={onConnect}
            onAddPath={onAddPath}
          />
        )}
        {nav}
      </div>
    </div>
  )
}

/** 剖面即預覽：七步各自打哪一支端點，按之前就攤開來（direction contract 的 Proof）。 */
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

/**
 * 版本太舊（brief §16.4、§19、§20.9）。**擺在最上面、在序列之前**：升級之前按幾次靠泊
 * 都是同一個結果，而升級是不可逆的，那幾件先做的事要在按之前就看得到。
 */
function VersionNotice({ version }: { version: string }) {
  const { t } = useTranslation()

  return (
    <div className="mt-4 grid gap-2">
      <Notice signal="blocked" label={t('jellyfin.version.label')}>
        {t('jellyfin.version.current', { version })}
      </Notice>
      <p className="max-w-prose text-xs text-ink-dim">{t('jellyfin.version.why')}</p>
      <p className="max-w-prose text-xs text-ink">{t('jellyfin.version.upgrade')}</p>
    </div>
  )
}

/** 既有服務的剖面：這台伺服器現在是什麼樣子，全部是它自己報出來的值。 */
function ServerCutaway({ setup }: { setup: JellyfinSetup }) {
  const { t } = useTranslation()
  const version = setup.version

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
    </Cutaway>
  )
}

/**
 * 靠泊序列：九條纜繩。整份結果在請求回來時一次到位，但每一步在後端做之前就把自己標成
 * `running` 並存下來，所以請求還在飛的時候前端輪詢就看得到序列走到哪裡。
 */
function BootstrapSequence({
  setup,
  draft,
  running,
  failed,
  onBootstrap,
  redetect,
}: {
  setup: JellyfinSetup
  draft: LibraryDraftState
  running: boolean
  failed: boolean
  onBootstrap: (libraries: LibraryDraft[]) => void
  redetect?: ReactNode
}) {
  const { t } = useTranslation()
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  const started = setup.steps.length > 0
  const broke = setup.steps.find((row) => row.status === 'failed')
  const done = started && !running && setup.steps.every((row) => isSettled(row.status))
  // 清單還有標紅的格子就不靠泊：建出來的會是使用者沒打算要的那一份（票 06f）。
  const blocked = draft.blocked && !running
  const run = () => onBootstrap(draft.drafts)

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
            {t('jellyfin.bundled.done', {
              count: setup.bundled.filter((row) => row.built).length,
            })}
          </Notice>
        </div>
      )}

      {failed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('jellyfin.bundled.requestFailed')}
          </Notice>
          {redetect && <div className="mt-3">{redetect}</div>}
        </div>
      )}

      {/* 做完了，「前往下一個泊位」接手主要動作與底部的位置（`BerthNav`）。 */}
      <div className={`mt-6 ${done ? '' : STICKY_ACTION}`}>
        {blocked && (
          <p className="mb-3 text-xs text-blocked-ink">{t('jellyfin.bundled.list.blocked')}</p>
        )}
        {done ? (
          <GhostButton type="button" busy={running} disabled={blocked} onClick={run}>
            {t('jellyfin.bundled.rerun')}
          </GhostButton>
        ) : (
          <PrimaryButton type="button" busy={running} disabled={blocked} onClick={run}>
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

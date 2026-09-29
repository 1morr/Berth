import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { JELLYFIN_STEPS, type JellyfinSetup, type LibraryDraft } from '../api/setup'
import { type SetupStep } from '../api/schemas'
import { STICKY_ACTION, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { BundledLibraries } from './BundledLibraries'
import { useLibraryDraft, type LibraryDraftState } from './useLibraryDraft'
import { StepLine } from '../components/StepLine'
import { isSettled } from '../components/steps'
import { STEP_ENDPOINT, STEP_FIX, STEP_LABEL, isJellyfinStep, manualSteps } from './jellyfinSteps'
import { StepFrame } from './StepFrame'

/**
 * 頁 3 的前半：套件內 Jellyfin 的媒體庫（plan §9.3 頁 3、§9.4，票 06f；M4 票 15 從 Jellyfin 頁搬過來）。
 *
 * 剖面是七步各打哪一支端點；工作面是一張要建的媒體庫清單，一顆按鈕跑完建媒體庫那一步，畫面逐條纜繩
 * 顯示結果與實測值（前六步在頁 1 成立擁有者時就有結論了）。**只給套件內**：既有 Jellyfin 絕不自動建
 * 媒體庫（brief §16.4），它的頁 3 直接是 Route，「加入 Berth 路徑」在 Route 的勾選表上。
 */
export function JellyfinStep({
  setup,
  running,
  bootstrapFailed,
  onBootstrap,
  onSaveLibraries,
  savingLibraries,
  saveLibrariesFailed,
  note,
  nav,
}: {
  setup: JellyfinSetup
  running: boolean
  /** 請求本身沒跑完（後端沒回應）。步驟自己的失敗在 `setup.steps` 裡，各自貼在它那一行。 */
  bootstrapFailed: boolean
  /** 帶著剖面上的清單：先存它，再跑序列（`bootstrap` 讀的是存下來的那一份）。 */
  onBootstrap: (libraries: LibraryDraft[]) => void
  /** 剖面停手一會兒就存（票 06f）。 */
  onSaveLibraries: (libraries: LibraryDraft[]) => void
  savingLibraries: boolean
  /** 清單存不下來的那一句，沒有就是 `null`。 */
  saveLibrariesFailed: string | null
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  // 它只在清單真的被改過時才存。
  const draft = useLibraryDraft(setup, onSaveLibraries)

  return (
    <StepFrame cutaway={<SequenceCutaway />}>
      <h2 className="text-lg font-semibold text-ink">{t('jellyfin.bundled.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('jellyfin.bundled.lede')}</p>
      {note}

      {!setup.version_supported && <VersionNotice version={setup.version} />}

      {/* 清單是這一步的輸入，排在「開始靠泊」之前（票 06h：原本在左欄剖面，工作面搬到 DOM
          前面之後，Tab 會先到右欄的鍵、再回頭到清單）。 */}
      <div className="mt-6">
        <BundledLibraries
          draft={draft}
          libraryRoot={setup.library_root}
          locked={running}
          saving={savingLibraries}
          saveFailed={saveLibrariesFailed}
        />
      </div>

      <BootstrapSequence
        setup={setup}
        draft={draft}
        running={running}
        failed={bootstrapFailed}
        onBootstrap={onBootstrap}
      />
      {nav}
    </StepFrame>
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
}: {
  setup: JellyfinSetup
  draft: LibraryDraftState
  running: boolean
  failed: boolean
  onBootstrap: (libraries: LibraryDraft[]) => void
}) {
  const { t } = useTranslation()
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  const broke = setup.steps.find((row) => row.status === 'failed')
  // 前六步在第 1 步（擁有者）就有結論了（M4 票 06），這一格做完的是建媒體庫那一步。
  const done =
    !running &&
    byStep.get('libraries') !== undefined &&
    setup.steps.every((row) => isSettled(row.status))
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

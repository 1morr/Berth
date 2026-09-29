import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import {
  QBITTORRENT_STEPS,
  type InterfaceLogin,
  type InterfaceLoginRefusal,
  type QbittorrentStep as QbittorrentStepKey,
  type SetupStatus,
} from '../api/setup'
import { type QbittorrentSetup, type SetupStep } from '../api/schemas'
import { STICKY_ACTION, CopyLine, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { StepLine } from '../components/StepLine'
import { isSettled } from '../components/steps'
import { useInterfaceLogin } from './interfaceLogin'
import { BerthLogin } from './InterfaceLoginFields'
import { STEP_FIX, STEP_LABEL } from './qbittorrentSteps'
import { ServiceChoice, type ChoiceControls } from './ServiceChoice'
import { useChoiceDraft } from './choiceDraft'
import { connected } from './signals'
import { StepFrame } from './StepFrame'

/**
 * 頁 2：qBittorrent（plan §9.3）。
 *
 * 頁首是二選一（M4 票 15，`ServiceChoice`）：不預選、選了才連。連上之後才有這一頁自己的事——
 * 剖面列**逐鍵的差異**：現值在左、建議值在右，一眼看得出按下去會改掉什麼。套用只寫有差異的鍵，
 * 本來就對的那幾條是「已經是這樣」。
 *
 * **既有的那一台一個鍵都不寫**（`writes_preferences`，M4 票 05）：剖面照樣列，但說的是
 * 「不會寫入」，按鈕只是確認連得上、版本夠新。
 *
 * **套件內的那一台多一組 WebUI 登入**（`web_ui_login`，M4 票 07）：跟著「套用」送出，必填；預設
 * 「沿用 Jellyfin 帳密」（M4 票 15）。那一台自己就設過的不強迫再設（`web_ui_username` 已經有值）。
 */
export function QbittorrentStep({
  status,
  setup,
  setupFailed,
  owner,
  applying,
  requestFailed,
  loginRefusal,
  onApply,
  choice,
  note,
  nav,
}: {
  status: SetupStatus
  /** 連上之後才讀：選之前一個請求都不發（M4 票 15）。 */
  setup: QbittorrentSetup | undefined
  setupFailed: boolean
  /** 擁有者的名字：沿用 Jellyfin 帳密時的帳號，取消勾選時預填它。 */
  owner: string
  applying: boolean
  /** 請求本身沒跑完。逐鍵的失敗在 `setup.steps` 裡，各自貼在它那一行。 */
  requestFailed: boolean
  /** 沿用 Jellyfin 帳密而 Jellyfin 那一關沒過：什麼都沒寫。 */
  loginRefusal: InterfaceLoginRefusal | null
  /**
   * `login` 是頁上填的 WebUI 登入；`null` 是登入照舊（設過了、沒按「更換」）。
   * 回傳的 promise 成功之後欄位清掉密碼、收起來。
   */
  onApply: (login: InterfaceLogin | null) => Promise<unknown>
  choice: ChoiceControls
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const service = status.services.find((row) => row.kind === 'qbittorrent')
  const choiceDraft = useChoiceDraft()
  // 標題與 lede 跟著畫面上選著的那一格：換另一格還在確認時就說那一格的事（M4 票 09）。
  const draft = choiceDraft.draft !== service?.origin ? choiceDraft.draft : null
  const switching = draft !== null
  const mode = draft
    ? draft
    : !service
      ? 'choose'
      : setup?.writes_preferences === false
        ? 'existing'
        : 'bundled'
  const ready = connected(service) && !switching

  return (
    <StepFrame cutaway={setup && ready ? <DiffCutaway setup={setup} /> : <ChoiceCutaway />}>
      <h2 className="text-lg font-semibold text-ink">{t(`qbittorrent.title.${mode}`)}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t(`qbittorrent.lede.${mode}`)}</p>
      {note}

      <ServiceChoice
        kind="qbittorrent"
        status={status}
        {...choice}
        {...choiceDraft}
        switchWarning={
          setup && setup.steps.length > 0 ? t('choice.switchWarning.qbittorrent') : undefined
        }
      />

      {ready &&
        (setup ? (
          setup.blocked ? (
            <Blocked setup={setup} />
          ) : (
            <ApplySequence
              key={`${service?.origin}:${service?.base_url}`}
              setup={setup}
              owner={owner}
              applying={applying}
              requestFailed={requestFailed}
              loginRefusal={loginRefusal}
              onApply={onApply}
            />
          )
        ) : (
          <p className="mt-6 text-sm text-ink-dim">
            {setupFailed ? t('qbittorrent.unreachable') : t('health.checking')}
          </p>
        ))}
      {nav}
    </StepFrame>
  )
}

/** 還沒選（或還沒連上）時的剖面：兩種來源各會做什麼。 */
function ChoiceCutaway() {
  const { t } = useTranslation()

  return (
    <Cutaway title={t('owner.cutaway.title')}>
      <CutawayRow term={t('origin.bundled')} value={t('qbittorrent.cutaway.bundledPlan')} />
      <CutawayRow term={t('origin.existing')} value={t('qbittorrent.cutaway.existingPlan')} />
    </Cutaway>
  )
}

/** 剖面即預覽：現值與建議值並排，值貼在它那一行（direction contract）。 */
function DiffCutaway({ setup }: { setup: QbittorrentSetup }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-6">
      <Cutaway title={t('qbittorrent.cutaway.server')}>
        <CutawayRow term={t('connect.field.baseUrl')} value={setup.base_url || '—'} />
        <CutawayRow
          term={t('detail.version')}
          value={setup.version || '—'}
          muted={!setup.version}
        />
        <CutawayRow
          term={t('qbittorrent.cutaway.webapi')}
          value={setup.webapi_version || '—'}
          muted={!setup.webapi_version}
        />
        <CutawayRow
          term={t('qbittorrent.cutaway.password')}
          value={
            !setup.web_ui_login
              ? t('qbittorrent.cutaway.existingLogin')
              : setup.web_ui_username || t('qbittorrent.cutaway.willSet')
          }
          muted={!setup.web_ui_username}
        />
      </Cutaway>

      {setup.diffs.length > 0 && (
        <section className="border-2 border-rule bg-well">
          <h3 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
            {t(
              setup.writes_preferences
                ? 'qbittorrent.cutaway.diff'
                : 'qbittorrent.cutaway.reference',
            )}
          </h3>
          <table className="w-full table-fixed border-collapse text-left">
            <thead>
              <tr className="border-b-2 border-rule">
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t('qbittorrent.cutaway.key')}
                </th>
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t('qbittorrent.cutaway.current')}
                </th>
                <th scope="col" className="label px-4 py-2 text-ink-dim">
                  {t(
                    setup.writes_preferences
                      ? 'qbittorrent.cutaway.recommended'
                      : 'qbittorrent.cutaway.bundledValue',
                  )}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {setup.diffs.map((row) => (
                <tr key={row.key}>
                  <th
                    scope="row"
                    className="value px-4 py-3 text-xs font-normal wrap-anywhere text-ink-dim"
                  >
                    {row.key}
                  </th>
                  <td
                    className={`value px-4 py-3 text-xs wrap-anywhere ${
                      row.differs ? 'text-ink' : 'text-ink-dim'
                    }`}
                  >
                    {row.current || '—'}
                  </td>
                  <td className="value px-4 py-3 text-xs font-semibold wrap-anywhere text-ink">
                    {row.differs ? row.recommended : t('qbittorrent.cutaway.same')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

/** 版本太舊或連不上：這一步做不下去，畫面給的是升級 / 排查的路，不是一顆按不動的按鈕。 */
function Blocked({ setup }: { setup: QbittorrentSetup }) {
  const { t } = useTranslation()
  const tooOld = !setup.supported && setup.reachable

  return (
    <div className="mt-6 grid gap-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {tooOld
          ? t('qbittorrent.blocked.tooOld', { version: setup.version || '—' })
          : t('qbittorrent.blocked.unreachable')}
      </Notice>
      {setup.error && (
        <p role="alert" className="value max-w-prose wrap-anywhere text-xs text-blocked-ink">
          {setup.error}
        </p>
      )}
      <div>
        <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
        <p className="mt-2 max-w-prose text-xs text-ink-dim">
          {tooOld ? t('qbittorrent.blocked.upgrade') : t('connect.fix.unreachable')}
        </p>
        <div className="mt-2 grid grid-cols-1 gap-px">
          {(tooOld
            ? ['docker compose pull qbittorrent', 'docker compose up -d qbittorrent']
            : ['docker compose ps qbittorrent', 'docker compose logs --tail 50 qbittorrent']
          ).map((command) => (
            <CopyLine key={command} command={command} />
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * 靠泊序列：一個鍵一條纜繩。已經是建議值的那幾條也繫上，只是沒有被寫過。
 *
 * 既有的那一台沒有纜繩可列——五個鍵都不寫、密碼也不設，列出來只會是一排「已經是這樣」，
 * 說的是假話。它只剩一顆確認鍵與做完之後的那一句。
 */
function ApplySequence({
  setup,
  owner,
  applying,
  requestFailed,
  loginRefusal,
  onApply,
}: {
  setup: QbittorrentSetup
  owner: string
  applying: boolean
  requestFailed: boolean
  loginRefusal: InterfaceLoginRefusal | null
  onApply: (login: InterfaceLogin | null) => Promise<unknown>
}) {
  const { t } = useTranslation()
  const login = useInterfaceLogin({ current: setup.web_ui_username, owner })

  function apply() {
    const taken = setup.web_ui_login ? login.take() : null
    if (taken === undefined) return
    // 請求沒走完的那一句由 `requestFailed` 說；欄位留著，改一個字再按。
    onApply(taken).then(
      () => taken && login.reset(taken.username ?? ''),
      () => undefined,
    )
  }
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  const started = setup.steps.length > 0
  const done = started && !applying && setup.steps.every((row) => isSettled(row.status))
  const pending = setup.diffs.filter((row) => row.differs).length
  const writes = setup.writes_preferences

  return (
    <>
      {setup.temp_path_warning && (
        <div className="mt-4">
          <Notice signal="assigned" label={t('common.warning')}>
            {t('qbittorrent.warning.tempPath')}
          </Notice>
        </div>
      )}

      {setup.web_ui_login && (
        <div className="mt-6">
          <BerthLogin service="qbittorrent" current={setup.web_ui_username} form={login} />
        </div>
      )}

      {writes && (
        <ol
          aria-live="polite"
          aria-busy={applying}
          className="mt-6 grid gap-3"
          data-testid="sequence"
        >
          {QBITTORRENT_STEPS.map((step) => (
            <QbittorrentLine
              key={step}
              step={step}
              row={byStep.get(step)}
              baseUrl={setup.base_url}
            />
          ))}
        </ol>
      )}

      {done && (
        <div className="mt-4">
          <Notice signal="secured" label={t('status.ok')}>
            {t(writes ? 'qbittorrent.done' : 'qbittorrent.doneExisting')}
          </Notice>
        </div>
      )}

      {requestFailed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {loginRefusal
              ? t(`interfaceLogin.refused.${loginRefusal.reason}`, { owner })
              : t('qbittorrent.requestFailed')}
          </Notice>
        </div>
      )}

      <div className={`mt-6 ${done ? '' : STICKY_ACTION}`}>
        {done ? (
          <GhostButton type="button" busy={applying} onClick={apply}>
            {t(writes ? 'qbittorrent.rerun' : 'qbittorrent.recheck')}
          </GhostButton>
        ) : (
          <PrimaryButton type="button" busy={applying} onClick={apply}>
            {applying
              ? t(writes ? 'qbittorrent.applying' : 'qbittorrent.checking')
              : writes
                ? t('qbittorrent.apply', { keys: pending })
                : t('qbittorrent.confirm')}
          </PrimaryButton>
        )}
      </div>
    </>
  )
}

/** 一條纜繩：一個偏好鍵。`step` 是封閉集合，所以標題與說明都是查表，不必有 fallback。 */
function QbittorrentLine({
  step,
  row,
  baseUrl,
}: {
  step: QbittorrentStepKey
  row: SetupStep | undefined
  baseUrl: string
}) {
  const { t } = useTranslation()

  return (
    <StepLine
      label={t(STEP_LABEL[step])}
      endpoint={step}
      row={row}
      fix={t(STEP_FIX[step])}
      commands={[`${baseUrl}/#/settings`]}
    />
  )
}

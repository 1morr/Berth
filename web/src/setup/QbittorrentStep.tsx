import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { QBITTORRENT_STEPS, type QbittorrentStep as QbittorrentStepKey } from '../api/setup'
import { type QbittorrentSetup, type SetupStep } from '../api/schemas'
import { STICKY_ACTION, CopyLine, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { StepLine } from '../components/StepLine'
import { isSettled } from '../components/steps'
import { STEP_FIX, STEP_LABEL } from './qbittorrentSteps'
import { StepFrame } from './StepFrame'

/**
 * 泊位 2：qBittorrent（plan §9.3 第 4 步）。
 *
 * 剖面列的是**逐鍵的差異**：現值在左、建議值在右，一眼看得出按下去會改掉什麼。
 * 套用只寫有差異的鍵，本來就對的那幾條是「已經是這樣」。
 */
export function QbittorrentStep({
  setup,
  applying,
  requestFailed,
  onApply,
  note,
  nav,
  redetect,
}: {
  setup: QbittorrentSetup
  applying: boolean
  /** 請求本身沒跑完。逐鍵的失敗在 `setup.steps` 裡，各自貼在它那一行。 */
  requestFailed: boolean
  onApply: () => void
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
  /** 連不上時的「重新偵測這個服務」（票 06d）。 */
  redetect?: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <StepFrame cutaway={<DiffCutaway setup={setup} />}>
      <h2 className="text-lg font-semibold text-ink">{t('qbittorrent.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(setup.origin === 'bundled' ? 'qbittorrent.lede.bundled' : 'qbittorrent.lede.existing')}
      </p>
      {note}

      {setup.blocked ? (
        <Blocked setup={setup} redetect={redetect} />
      ) : (
        <ApplySequence
          setup={setup}
          applying={applying}
          requestFailed={requestFailed}
          onApply={onApply}
        />
      )}
      {nav}
    </StepFrame>
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
          value={t(setup.sets_password ? 'qbittorrent.cutaway.willSet' : 'admin.cutaway.skipped')}
          muted={!setup.sets_password}
        />
      </Cutaway>

      {setup.diffs.length > 0 && (
        <section className="border-2 border-rule bg-well">
          <h3 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink-dim">
            {t('qbittorrent.cutaway.diff')}
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
                  {t('qbittorrent.cutaway.recommended')}
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
function Blocked({ setup, redetect }: { setup: QbittorrentSetup; redetect?: ReactNode }) {
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
      {/* 連不上的那一種：改好 compose、把容器叫起來之後，在這一格就地重探。 */}
      {!tooOld && redetect && <div>{redetect}</div>}
    </div>
  )
}

/** 靠泊序列：一個鍵一條纜繩。已經是建議值的那幾條也繫上，只是沒有被寫過。 */
function ApplySequence({
  setup,
  applying,
  requestFailed,
  onApply,
}: {
  setup: QbittorrentSetup
  applying: boolean
  requestFailed: boolean
  onApply: () => void
}) {
  const { t } = useTranslation()
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  const started = setup.steps.length > 0
  const done = started && !applying && setup.steps.every((row) => isSettled(row.status))
  const pending = setup.diffs.filter((row) => row.differs).length

  return (
    <>
      {setup.temp_path_warning && (
        <div className="mt-4">
          <Notice signal="assigned" label={t('common.warning')}>
            {t('qbittorrent.warning.tempPath')}
          </Notice>
        </div>
      )}

      <ol
        aria-live="polite"
        aria-busy={applying}
        className="mt-6 grid gap-3"
        data-testid="sequence"
      >
        {QBITTORRENT_STEPS.map((step) => (
          <QbittorrentLine key={step} step={step} row={byStep.get(step)} baseUrl={setup.base_url} />
        ))}
      </ol>

      {done && (
        <div className="mt-4">
          <Notice signal="secured" label={t('status.ok')}>
            {t('qbittorrent.done')}
          </Notice>
        </div>
      )}

      {requestFailed && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t('qbittorrent.requestFailed')}
          </Notice>
        </div>
      )}

      <div className={`mt-6 ${done ? '' : STICKY_ACTION}`}>
        {done ? (
          <GhostButton type="button" busy={applying} onClick={onApply}>
            {t('qbittorrent.rerun')}
          </GhostButton>
        ) : (
          <PrimaryButton type="button" busy={applying} onClick={onApply}>
            {applying ? t('qbittorrent.applying') : t('qbittorrent.apply', { keys: pending })}
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

import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import {
  QBITTORRENT_STEPS,
  type InterfaceLogin,
  type InterfaceLoginRefusal,
  type QbittorrentStep as QbittorrentStepKey,
  type SetupStatus,
} from '../api/setup'
import { type QbittorrentSetup, type SetupStep } from '../api/schemas'
import { STICKY_ACTION, CopyLine, Notice, PrimaryButton } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { failureText } from '../components/failures'
import { RequestFailed } from '../components/RequestFailed'
import { StepLine } from '../components/StepLine'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { carriedUnfit, useCarriedLogin, useInterfaceLogin } from './interfaceLogin'
import { BerthLogin, CarriedApplying, CarriedUnfit } from './InterfaceLoginFields'
import { STEP_FIX, STEP_LABEL } from './qbittorrentSteps'
import { ServiceChoice, type ChoiceControls } from './ServiceChoice'
import type { ChoiceDraft } from './choiceDraft'
import { qbittorrentWeb } from './serviceWeb'
import { VERSION_FLOOR, connected } from './signals'
import { StepFrame } from './StepFrame'

/**
 * 頁 2：qBittorrent（plan §9.3）。
 *
 * 頁首是二選一（M4 票 15，`ServiceChoice`）：不預選、選了才連。連上之後剖面是那一台的位址、版本與
 * 介面登入。
 *
 * **兩種來源都不寫全域偏好**（M4 票 32，brief §19 D2）：Berth 送單逐個 torrent 帶自己的分類與
 * `autoTMM=true`，全域的哪一個鍵都不影響它。
 *
 * **測試通過就做完，沒有不寫入的確認鍵**（M4 票 38，brief §19 D5）：既有的那一台連上即完成；套件內的
 * 那一台多一組 WebUI 登入（`web_ui_login`，M4 票 07），必填、預設「沿用 Jellyfin 帳密」（M4 票 15），
 * 只有要寫它的時候才有「設定介面登入」那一顆。那一台自己就設過的不強迫再設（後端在連線測試時記下）。
 * 頁 1 勾了「也用這組」時不問，自動沿用那一組（`carriedPassword`，M4 票 40）。
 * 做完了沒照後端的頁序（`done`），與前進鍵同一個來源。
 */
export function QbittorrentStep({
  status,
  setup,
  setupFailed,
  owner,
  carriedPassword,
  applying,
  requestError,
  loginRefusal,
  onApply,
  choice,
  done,
  note,
  nav,
}: {
  status: SetupStatus
  /** 連上之後才讀：選之前一個請求都不發（M4 票 15）。 */
  setup: QbittorrentSetup | undefined
  setupFailed: boolean
  /** 擁有者的名字：沿用 Jellyfin 帳密時的帳號，取消勾選時預填它。 */
  owner: string
  /** 頁 1 帶過來的擁有者密碼（只在這個分頁的記憶體裡，M4 票 40）；沒有就是 `null`。 */
  carriedPassword: string | null
  applying: boolean
  /** 請求本身沒跑完（沒有就是 `null`）。登入那一條的失敗在 `setup.steps` 裡，貼在它那一行。 */
  requestError: unknown
  /** 沿用 Jellyfin 帳密而 Jellyfin 那一關沒過：什麼都沒寫。 */
  loginRefusal: InterfaceLoginRefusal | null
  /**
   * `login` 是頁上填的 WebUI 登入；`null` 是登入照舊（設過了、沒按「更換」）。
   * 回傳的是套用之後的那一份；登入那一條過了，欄位才清掉密碼、收起來。
   */
  onApply: (login: InterfaceLogin | null) => Promise<QbittorrentSetup>
  /** 選擇的兩支 mutation 與畫面上選著、還沒存下的那一格（`SetupPage` 持有）。 */
  choice: ChoiceControls & ChoiceDraft
  /** 後端說頁 2 做完了（`_qbittorrent_secured`）。 */
  done: boolean
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const service = status.services.find((row) => row.kind === 'qbittorrent')
  // 標題與 lede 跟著畫面上選著的那一格：換另一格還在確認時就說那一格的事（M4 票 09）。
  const draft = choice.draft !== service?.origin ? choice.draft : null
  const switching = draft !== null
  // 照選下的來源說，不照那一台讀不讀得回來：既有的那一台連不上時，原本標題變成套件內那一句
  // （M4 票 21）。
  const mode = draft ?? service?.origin ?? 'choose'
  const ready = connected(service) && !switching

  return (
    <StepFrame cutaway={setup && ready ? <ServerCutaway setup={setup} /> : <ChoiceCutaway />}>
      <h2 className="text-lg font-semibold text-ink">{t(`qbittorrent.title.${mode}`)}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t(`qbittorrent.lede.${mode}`)}</p>
      {note}

      <ServiceChoice
        kind="qbittorrent"
        status={status}
        {...choice}
        // 選過一台就先確認：Route 檢查會作廢，而 Berth 可能已經在那一台建了分類（M4 票 47 列出來）。
        // 不看頁 2 的纜繩：既有的那一台沒有纜繩，分類卻照樣建在它上面。
        switchWarning={service ? t('choice.switchWarning.qbittorrent') : undefined}
      />

      {ready &&
        (setup ? (
          setup.blocked ? (
            <Blocked setup={setup} />
          ) : setup.web_ui_login ? (
            <LoginSequence
              key={`${service?.origin}:${service?.base_url}`}
              setup={setup}
              owner={owner}
              carriedPassword={carriedPassword}
              done={done}
              applying={applying}
              requestError={requestError}
              loginRefusal={loginRefusal}
              onApply={onApply}
            />
          ) : (
            done && <DoneNotice text={t('qbittorrent.doneExisting')} />
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

/** 連上之後的剖面：那一台是誰、介面登入由誰管（direction contract：值貼在它那一行）。 */
function ServerCutaway({ setup }: { setup: QbittorrentSetup }) {
  const { t } = useTranslation()

  return (
    <Cutaway title={t('qbittorrent.cutaway.server')}>
      <CutawayRow term={t('connect.field.baseUrl')} value={setup.base_url || '—'} />
      <CutawayRow term={t('detail.version')} value={setup.version || '—'} muted={!setup.version} />
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
  )
}

/**
 * 讀那一台時做不下去：版本太舊或連不上。畫面給的是升級 / 排查的路，不是一顆按不動的按鈕。
 *
 * **補法照來源**（M4 票 21）：`docker compose` 的指令只對套件內那一台成立；既有的那一台是使用者自己的
 * 容器，說的是「至少要 X，這一台是 Y」與去檢查位址。版本在測連線時就擋了（`setup._test_connection`），
 * 走到這裡的太舊只會是測過之後那一台被換了版本。
 */
function Blocked({ setup }: { setup: QbittorrentSetup }) {
  const { t } = useTranslation()
  const tooOld = !setup.supported && setup.reachable
  const bundled = setup.origin === 'bundled'
  const outdated = { floor: VERSION_FLOOR.qbittorrent, version: setup.version || '—' }
  const [fix, commands] = tooOld
    ? bundled
      ? [
          t('connection.fix.outdatedBundled', outdated),
          ['docker compose pull qbittorrent', 'docker compose up -d qbittorrent'],
        ]
      : [t('connection.fix.outdated', outdated), []]
    : bundled
      ? [
          t('connect.fix.unreachable'),
          ['docker compose ps qbittorrent', 'docker compose logs --tail 50 qbittorrent'],
        ]
      : [t('connection.fix.address'), []]

  return (
    <div className="mt-6 grid gap-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {tooOld
          ? t('qbittorrent.blocked.tooOld', { version: setup.version || '—' })
          : failureText(t, setup, 'qBittorrent')}
      </Notice>
      <div>
        <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
        <p className="mt-2 max-w-prose text-xs text-ink-dim">{fix}</p>
        {commands.length > 0 && (
          <div className="mt-2 grid grid-cols-1 gap-px">
            {commands.map((command) => (
              <CopyLine key={command} command={command} />
            ))}
          </div>
        )}
        <TechnicalDetails lines={[setup.base_url, setup.error]} />
      </div>
    </div>
  )
}

/** 這一頁做完了的那一句。 */
function DoneNotice({ text }: { text: string }) {
  const { t } = useTranslation()

  return (
    <div className="mt-4">
      <Notice signal="secured" label={t('status.ok')}>
        {text}
      </Notice>
    </div>
  )
}

/**
 * 靠泊序列：套件內那一台只有介面登入一條纜繩。既有的那一台沒有纜繩可列——什麼都不寫，列出來只會是
 * 一條「已經是這樣」，說的是假話。
 *
 * **主鍵只在有東西要寫時出現**（M4 票 38）：欄位開著（還沒設過、或按了「更換登入」）就是「設定介面
 * 登入」；已經設好而欄位收著時這一頁就做完了，不留一顆按下去什麼都不寫的鍵。
 */
function LoginSequence({
  setup,
  owner,
  carriedPassword,
  done,
  applying,
  requestError,
  loginRefusal,
  onApply,
}: {
  setup: QbittorrentSetup
  owner: string
  carriedPassword: string | null
  done: boolean
  applying: boolean
  requestError: unknown
  loginRefusal: InterfaceLoginRefusal | null
  onApply: (login: InterfaceLogin | null) => Promise<QbittorrentSetup>
}) {
  const { t } = useTranslation()
  // 頁 1 那一組不合 qBittorrent 的規則（M4 票 26）：不送，說為什麼，一開始就是自設的三格（M4 票 40）。
  const unfit = carriedUnfit('qbittorrent', carriedPassword, owner)
  const login = useInterfaceLogin({
    service: 'qbittorrent',
    current: setup.web_ui_username,
    owner,
    reuse: unfit === null,
  })
  // 送出那一刻的欄位版本：之後改了一格，上一次的失敗就不畫了（M4 票 21）。
  const [sentAt, setSentAt] = useState<number | null>(null)
  // 同一個請求還在飛（走開又回來，這一區重掛載）時不再送。
  const needed = !setup.web_ui_username && !applying
  const carriedLogin = useCarriedLogin({
    carriedPassword: unfit === null ? carriedPassword : null,
    needed,
    apply: (taken) => {
      setSentAt(login.edits)
      return onApply(taken)
    },
  })
  const failed = requestError !== null && requestError !== undefined && sentAt === login.edits

  function apply() {
    const taken = login.take()
    if (taken === undefined) return
    setSentAt(login.edits)
    // 請求沒走完的那一句由 `requestFailed` 說；欄位留著，改一個字再按。登入那一條沒過時也留著
    // （M4 票 26）：收起來就成了「帳號：xxx」，像是已經設好了。
    onApply(taken).then(
      (next) => taken && loginTook(next) && login.reset(taken.username ?? ''),
      () => undefined,
    )
  }
  const byStep = new Map(setup.steps.map((row) => [row.step, row]))
  // 登入那一條說的是送出那一刻的欄位（M4 票 26）：之後改了一格、換了沿用與否，它就不是這幾格的結果了，
  // 畫成還沒跑。進頁時（還沒送過）照後端存的那一次。
  if (login.edits !== (sentAt ?? 0)) byStep.delete(PASSWORD_STEP)
  const webUrl = qbittorrentWeb(setup)
  // 登入那一條過了也算做完：設好之後頁序要等 status 重讀回來，這段時間裡主鍵不該再冒出來。
  const settled = done || loginTook(setup)
  // 帳號讀得到而後端還沒記那一條（票 38 之前開始的精靈、或連線測試那一次沒讀到偏好）時欄位收著、頁還沒
  // 做完：這一顆送「登入照舊」，把那一條記下來。
  const showSetLogin = (login.open || !settled) && !carriedLogin.applying

  return (
    <>
      {unfit && !setup.web_ui_username && (
        <div className="mt-6">
          <CarriedUnfit owner={owner} problems={unfit} />
        </div>
      )}
      <div className="mt-6">
        {carriedLogin.applying ? (
          <CarriedApplying owner={owner} />
        ) : (
          <BerthLogin service="qbittorrent" current={setup.web_ui_username} form={login} />
        )}
      </div>

      <ol
        aria-live="polite"
        aria-busy={applying}
        className="mt-6 grid gap-3"
        data-testid="sequence"
      >
        {QBITTORRENT_STEPS.map((step) => (
          <QbittorrentLine key={step} step={step} row={byStep.get(step)} webUrl={webUrl} />
        ))}
      </ol>

      {settled && !applying && <DoneNotice text={t('qbittorrent.done')} />}

      {failed && (
        <div className="mt-4">
          {loginRefusal ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t(`interfaceLogin.refused.${loginRefusal.reason}`, { owner })}
            </Notice>
          ) : (
            <RequestFailed error={requestError} />
          )}
        </div>
      )}

      {showSetLogin && (
        <div className={`mt-6 ${STICKY_ACTION}`}>
          <PrimaryButton type="button" busy={applying} onClick={apply}>
            {applying ? t('qbittorrent.settingLogin') : t('qbittorrent.setLogin')}
          </PrimaryButton>
        </div>
      )}
    </>
  )
}

/** WebUI 登入那一條（後端的 `QbittorrentStep.PASSWORD`）。 */
const PASSWORD_STEP = 'web_ui_password' satisfies QbittorrentStepKey

/** 登入那一條過了：寫進去了，或已經是這一組。 */
function loginTook(next: QbittorrentSetup): boolean {
  const row = next.steps.find((each) => each.step === PASSWORD_STEP)
  return row?.status === 'ok' || row?.status === 'skipped'
}

/**
 * 一條纜繩。`step` 是封閉集合，所以標題與說明都是查表，不必有 fallback。
 *
 * 補法連到 qBittorrent 自己的設定頁，位址是瀏覽器開得了的那一個（`qbittorrentWeb`）；給不出就不給——
 * 原本連的是 compose 內網的 `http://qbittorrent:8080`（M4 票 26）。qBittorrent 不收那組帳密時不叫人去
 * 它的設定頁：同一條規則它那裡也擋，改的是這一頁上的欄位。
 */
function QbittorrentLine({
  step,
  row,
  webUrl,
}: {
  step: QbittorrentStepKey
  row: SetupStep | undefined
  webUrl: string | null
}) {
  const { t } = useTranslation()
  const rejected = row?.failure === 'login_rejected'

  return (
    <StepLine
      label={t(STEP_LABEL[step])}
      service="qBittorrent"
      endpoint={step}
      summary={row?.detail}
      row={row}
      fix={rejected ? t('qbittorrent.fix.loginRejected') : t(STEP_FIX[step])}
      commands={!rejected && webUrl ? [`${webUrl}/#/settings`] : []}
    />
  )
}

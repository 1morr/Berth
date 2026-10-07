import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  IndexerSetup,
  InterfaceLogin,
  InterfaceLoginRefusal,
  SetupService,
  SetupStatus,
} from '../api/setup'
import { GhostButton, Notice, PrimaryButton, TEXT_LINK } from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { failureText } from '../components/failures'
import { RequestFailed } from '../components/RequestFailed'
import { StepLine } from '../components/StepLine'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { AddedSites, AddSites, type SiteControls } from './IndexerSites'
import { useCarriedLogin, useInterfaceLogin } from './interfaceLogin'
import { BerthLogin, CarriedApplying } from './InterfaceLoginFields'
import { AdvancedSites, RecommendedSites } from './RecommendedSites'
import { prowlarrWeb } from './serviceWeb'
import { ServiceChoice, type ChoiceControls } from './ServiceChoice'
import type { ChoiceDraft } from './choiceDraft'
import { STEP } from './navigation'
import { GAP, modeOf } from './indexerGaps'
import { connected } from './signals'
import { StepFrame } from './StepFrame'

export type { SiteControls } from './IndexerSites'

/** 套件內頁 4 的主鍵（M4 票 44）：測推薦站、把通過的加進去。 */
export interface RecommendedControls {
  running: boolean
  /** 請求沒走完就 reject。 */
  onRun: () => Promise<IndexerSetup>
}

/** 套件內 Prowlarr 的介面登入（M4 票 20 從「加入」拆出來的那一區）。 */
export interface LoginControls {
  saving: boolean
  /** 沿用 Jellyfin 帳密而 Jellyfin 那一關沒過：什麼都沒寫。 */
  refusal: InterfaceLoginRefusal | null
  /** 請求沒走完就 reject。 */
  onSave: (login: InterfaceLogin) => Promise<IndexerSetup>
}

/**
 * 頁 4：Prowlarr 與索引站（plan §9.3，M4 票 15 併成一頁、票 09 改成先測再加）。
 *
 * 頁首是二選一（`ServiceChoice`），連上之後照接的是哪一種畫：
 *
 * - **套件內 Prowlarr**：「已加入」（`IndexerSites`）與主鍵「測試推薦站，加入通過的」（`RecommendedSites`，
 *   M4 票 44）；逐站測試與勾選、其他公開站收在「進階」。介面登入是自己的一區（`ProwlarrLogin`，M4 票 20），
 *   必填。
 * - **既有 Prowlarr**：同樣的「已加入」與「加站」，加的是使用者自己那一台，Berth 不移除（M4 票 20，
 *   使用者拍板：按一次確認）。**一站都沒有時這一頁待處理**（`NoSites`）：到 Prowlarr 加站後重新讀取、
 *   在這裡加推薦的公開站，或之後再說。位址與 key 的表單、測試那一條與補法是頁 1、2 那一份
 *   （`ServiceChoice`，M4 票 39）：送的是同一支 `POST /setup/services/prowlarr`。
 *
 * 整頁可以「之後再說」，連選都還沒選也可以。
 *
 * **資料與動作全部從 props 進來**：精靈跑完之後設定頁接手（票 06i），重用 `IndexerActions`。
 */
export function IndexerStep({
  status,
  indexers,
  indexersFailed,
  owner,
  carriedPassword,
  applying,
  recommended,
  login,
  onApply,
  onSkip,
  choice,
  sites,
  note,
  nav,
}: {
  status: SetupStatus
  /** 選之前也讀得到：後端還沒選時不去連 Prowlarr（`indexer.read_indexer_status`）。 */
  indexers: IndexerSetup | undefined
  indexersFailed: boolean
  /** 擁有者的名字：沿用 Jellyfin 帳密時的帳號，取消勾選時預填它。 */
  owner: string
  /** 頁 1 帶過來的擁有者密碼（只在這個分頁的記憶體裡，M4 票 40）；沒有就是 `null`。 */
  carriedPassword: string | null
  applying: boolean
  recommended: RecommendedControls
  login: LoginControls
  onApply: (indexers: string[]) => Promise<IndexerSetup>
  onSkip: () => void
  /** 選擇的兩支 mutation 與畫面上選著、還沒存下的那一格（`SetupPage` 持有）。 */
  choice: ChoiceControls & ChoiceDraft
  /** 測試、試搜與移除（`IndexerSites`）。 */
  sites: SiteControls
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 上一個 / 下一個泊位（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const service = status.services.find((row) => row.kind === 'prowlarr')
  // 標題與 lede 跟著畫面上選著的那一格：換另一格還在確認時就說那一格的事（票 15 critique）。
  const switching = choice.draft !== null && choice.draft !== service?.origin
  const origin = choice.draft ?? service?.origin
  const ready = connected(service) && !switching
  // 畫哪一種看這一份清單自己說的來源：剛選下去、清單還沒重讀回來時兩者不一致，那幾秒什麼都不畫，
  // 不閃另一種的文案（M4 票 20）。
  const mode = ready && indexers ? modeOf(indexers, service?.origin) : null
  const hasResults = Boolean(indexers && indexers.steps.length > 0)
  // 連上過、這一次讀清單卻失敗：說讀不到，不說成「沒有站」（M4 票 20 的 code-review）。套件內的也是
  // （M4 票 27）：Prowlarr 重新產生 key 之後連線卡還是綠的，原本整段消失、只剩「之後再說」。
  const unread = (mode === 'prowlarr' || mode === 'bundled') && Boolean(indexers?.error)
  const sticky = status.current_step <= STEP.indexer
  // 清單上有站、後端上一次連線測試記的卻是 0 站（使用者到 Prowlarr 自己的介面加了站再回來）：後端照那個
  // 數判斷這一頁做完了沒，不重測的話前進鍵不出現、「還差」也空著。自動重新測試一次（M4 票 27，頁 2 的
  // 票 25 同一個做法），只發一次、不管結果。
  //
  // **反過來也一樣**（M4 票 31，實測 #34）：在 Prowlarr 刪到 0 站再回來，後端仍記著 1 站、算這一頁做完了，
  // 畫面卻同時說「待處理」與「前往下一個泊位」。所以看的是兩個數不一致，而且後端已經走過這一頁時也看
  // ——那正是記錯的數讓它走過去的情形。每個數只重測一次：重測之後還對不上（例如測失敗）不再追。
  const listed = indexers?.sites.length ?? 0
  const stale =
    (mode === 'bundled' || mode === 'prowlarr') &&
    !unread &&
    status.current_step >= STEP.indexer &&
    listed !== Number(service?.detail || 0)
  const resynced = useRef<number | null>(null)
  const { onRetest, retesting } = choice
  useEffect(() => {
    if (!stale || resynced.current === listed || retesting) return
    resynced.current = listed
    onRetest(false)
  }, [stale, listed, retesting, onRetest])

  return (
    <StepFrame
      cutaway={
        indexers ? (
          <IndexerCutaway indexers={indexers} service={service} bundled={mode === 'bundled'} />
        ) : (
          <span aria-hidden />
        )
      }
    >
      <h2 className="text-lg font-semibold text-ink">{t('indexer.title')}</h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(`indexer.lede.${origin ?? 'choose'}`)}
      </p>
      {note}

      <ServiceChoice
        kind="prowlarr"
        status={status}
        {...choice}
        switchWarning={hasResults ? t('choice.switchWarning.prowlarr') : undefined}
      />

      {indexers && unread && (
        <ReadFailed
          indexers={indexers}
          rereading={choice.retesting}
          onReread={() => choice.onRetest(true)}
        />
      )}
      {indexers && (mode === 'bundled' || mode === 'prowlarr') && !unread && (
        <>
          {mode === 'prowlarr' && indexers.sites.length === 0 && (
            <NoSites
              indexers={indexers}
              rereading={choice.retesting}
              onReread={() => choice.onRetest(true)}
            />
          )}
          {indexers.sites.length > 0 && <AddedSites indexers={indexers} controls={sites} />}
          {mode === 'bundled' ? (
            <>
              <RecommendedSites
                indexers={indexers}
                running={recommended.running}
                held={login.saving || applying}
                sticky={sticky}
                onRun={recommended.onRun}
                onSkip={onSkip}
              />
              <AdvancedSites>
                <AddSites
                  indexers={indexers}
                  applying={applying}
                  controls={sites}
                  onApply={onApply}
                  held={login.saving || recommended.running}
                  sticky={false}
                  advanced
                />
              </AdvancedSites>
            </>
          ) : (
            <AddSites
              indexers={indexers}
              applying={applying}
              controls={sites}
              onApply={onApply}
              onSkip={onSkip}
              sticky={sticky}
            />
          )}
          {mode === 'bundled' && (
            <ProwlarrLogin
              indexers={indexers}
              owner={owner}
              carriedPassword={carriedPassword}
              controls={login}
              held={recommended.running || applying}
            />
          )}
        </>
      )}
      {indexersFailed && <p className="mt-6 text-sm text-ink-dim">{t('indexer.unreachable')}</p>}

      {/* 選之前、或讀不到清單時，「之後再說」在這裡；Prowlarr 的在「加入」旁邊。 */}
      {((mode !== 'bundled' && mode !== 'prowlarr') || unread) && (
        <div className="mt-6">
          <GhostButton type="button" busy={applying} onClick={onSkip}>
            {t('indexer.skip')}
          </GhostButton>
        </div>
      )}

      {nav}
    </StepFrame>
  )
}

/**
 * 既有 Prowlarr 一站都沒有（M4 票 20）：Berth 什麼都搜不到，這一頁還沒完。說出三條路——到 Prowlarr
 * 加站後重新讀取、在下面加推薦的公開站、或之後再說——連結用瀏覽器開得了的位址（`prowlarrWeb`）。
 */
function NoSites({
  indexers,
  rereading,
  onReread,
}: {
  indexers: IndexerSetup
  rereading: boolean
  onReread: () => void
}) {
  const { t } = useTranslation()
  const webUrl = prowlarrWeb(indexers)

  return (
    <section className="mt-6 grid gap-3" data-testid="no-sites">
      <Notice signal="assigned" label={t('indexer.empty.label')}>
        {t('indexer.empty.body')}
      </Notice>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <GhostButton type="button" busy={rereading} onClick={onReread}>
          {rereading ? t('indexer.empty.rereading') : t('indexer.empty.reread')}
        </GhostButton>
        {webUrl && (
          <a
            href={`${webUrl}/#/indexers`}
            target="_blank"
            rel="noreferrer noopener"
            className={`${TEXT_LINK} text-sm`}
          >
            {t('indexer.add.openProwlarr')}
          </a>
        )}
      </div>
    </section>
  )
}

/** Prowlarr 的站清單這一次讀不到：原文與「重新讀取」（重測那一台，清單跟著重讀）。 */
function ReadFailed({
  indexers,
  rereading,
  onReread,
}: {
  indexers: IndexerSetup
  rereading: boolean
  onReread: () => void
}) {
  const { t } = useTranslation()

  return (
    <section className="mt-6 grid gap-3" data-testid="read-failed">
      <Notice signal="blocked" label={t('common.failed')}>
        {t('indexer.readFailed')} {failureText(t, indexers, 'Prowlarr')}{' '}
        {/* 套件內那一台的 key 被拒：重新讀取就是重讀掛載的 key（M4 票 27），照做就好。 */}
        {t(
          indexers.origin === 'bundled' && indexers.failure === 'auth_rejected'
            ? 'indexer.rereadKey'
            : 'indexer.rereadLater',
        )}
      </Notice>
      <TechnicalDetails lines={[indexers.base_url, indexers.error]} />
      <div>
        <GhostButton type="button" busy={rereading} onClick={onReread}>
          {rereading ? t('indexer.empty.rereading') : t('indexer.empty.reread')}
        </GhostButton>
      </div>
    </section>
  )
}

/**
 * 套件內 Prowlarr 的介面登入：自己的一區、自己的按鈕（M4 票 20），不跟著「加入」送。
 *
 * **必填**（M4 票 07 shape）：Prowlarr 現行版本不讓介面沒有登入——沒設的話，第一次打開它會跳出關不掉的
 * 視窗要人設一組（v2.6.5 `Page.js` 在驗證沒開時掛 `AuthenticationRequiredModal`，沒有關閉鈕）。精靈在
 * 這一條有結論之前停在頁 4（後端 `_indexer_settled`）。頁 1 勾了「也用這組」時不問，自動沿用那一組
 * （`carriedPassword`，M4 票 40）。
 */
function ProwlarrLogin({
  indexers,
  owner,
  carriedPassword,
  controls,
  held,
}: {
  indexers: IndexerSetup
  owner: string
  carriedPassword: string | null
  controls: LoginControls
  /**
   * 加站還在飛（M4 票 44）：設完登入 Prowlarr 會自行重啟，正在加的站撞上它，整批結論就丟了。等它回來才送，
   * 與加站那一邊的 `held` 互相讓。
   */
  held: boolean
}) {
  const { t } = useTranslation()
  const form = useInterfaceLogin({
    service: 'prowlarr',
    current: indexers.web_ui_username,
    owner,
  })
  // 與後端的 `PROWLARR_LOGIN_STEP` 同一個字串：那一條不是站。
  const row = indexers.steps.find((step) => step.step === 'prowlarr_login')
  const webUrl = prowlarrWeb(indexers)
  // 送出那一刻的欄位版本：之後改了一格，上一次的拒絕就不畫了（M4 票 21）。
  const [sentAt, setSentAt] = useState<number | null>(null)
  // 請求本身沒走完（Berth 停著、5xx）：原本這一支的 reject 被吞掉，按下去什麼都沒發生（M4 票 31，
  // 實測 #21）。說得出理由的拒絕（`refusal`）照舊由它說，這裡只接其餘的。
  const [failed, setFailed] = useState<unknown>(null)
  // Prowlarr 沒有帳密規則（`LOGIN_RULES`），頁 1 那一組一定能沿用；頁 2 的 `carriedUnfit` 這裡不必。
  const carriedLogin = useCarriedLogin({
    carriedPassword,
    // 同一個請求還在飛（走開又回來，這一區重掛載）時不再送。
    needed: !indexers.web_ui_username && !controls.saving && !held,
    apply: (taken) => {
      setSentAt(form.edits)
      setFailed(null)
      return controls.onSave(taken).catch((error: unknown) => setFailed(error))
    },
  })

  function save() {
    const taken = form.take()
    if (!taken) return
    setSentAt(form.edits)
    setFailed(null)
    controls.onSave(taken).then(
      () => form.reset(taken.username || owner),
      (error: unknown) => setFailed(error),
    )
  }

  return (
    <section
      id={GAP.login.target}
      // 前進鍵位置的「還差」把焦點送到這裡（M4 票 27）。
      tabIndex={-1}
      className="mt-10 border-t-2 border-rule pt-6"
      data-testid="prowlarr-login"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="label text-ink-dim">{t('interfaceLogin.prowlarr.legend')}</h3>
        <span className="label border-2 border-rule px-2 py-1 text-ink-dim">
          {t('indexer.login.required')}
        </span>
      </div>
      <div className="mt-4">
        {carriedLogin.applying ? (
          <CarriedApplying owner={owner} />
        ) : (
          <BerthLogin service="prowlarr" current={indexers.web_ui_username} form={form} />
        )}
      </div>
      {controls.refusal && sentAt === form.edits && (
        <div className="mt-4">
          <Notice signal="blocked" label={t('common.failed')}>
            {t(`interfaceLogin.refused.${controls.refusal.reason}`, { owner })}
          </Notice>
        </div>
      )}
      {failed !== null && !controls.refusal && sentAt === form.edits && (
        <div className="mt-4">
          <RequestFailed error={failed} />
        </div>
      )}
      {form.open && !carriedLogin.applying && (
        <div className="mt-4">
          <PrimaryButton type="button" busy={controls.saving} disabled={held} onClick={save}>
            {controls.saving ? t('indexer.login.saving') : t('indexer.login.save')}
          </PrimaryButton>
        </div>
      )}
      {/* 設下去的成敗要看得到（brief §16.3）；沒設過時是一條待處理。 */}
      {row && (
        <ol className="mt-6 grid gap-3">
          <StepLine
            label={t('indexer.add.login')}
            service="Prowlarr"
            endpoint="PUT /api/v1/config/host"
            summary={row.detail}
            row={row}
            fix={t('indexer.add.loginFix')}
            commands={webUrl ? [`${webUrl}/#/settings/general`] : []}
          />
        </ol>
      )}
    </section>
  )
}

/**
 * 設定頁的索引站那一區（票 06i）：已加入 + 加站。位址與 key 在它上面的連線區改（`ServiceConnection`，
 * M4 票 39：與精靈同一份表單、同一支端點）；介面登入在它自己的那一區（M4 票 07）。清單讀不到時與精靈頁 4
 * 同一段（`ReadFailed`，M4 票 54）：套件內那一台的 key 換了，「重新讀取」就是重讀掛載的 key。
 */
export function IndexerActions({
  indexers,
  applying,
  onApply,
  sites,
  rereading,
  onReread,
}: {
  indexers: IndexerSetup
  applying: boolean
  onApply: (indexers: string[]) => Promise<IndexerSetup>
  sites: SiteControls
  rereading: boolean
  onReread: () => void
}) {
  const { t } = useTranslation()
  // 既有的那一台連不上由上面測試那一條說；0 站的既有 Prowlarr 是待處理（M4 票 20），也算連上。
  const connected =
    indexers.origin === 'bundled' ||
    indexers.steps.some(
      (row) => row.step === 'prowlarr' && row.status !== 'failed' && row.status !== 'running',
    )

  if (!connected) return <p className="text-sm text-ink-dim">{t('indexer.connectFirst')}</p>
  if (indexers.error) {
    return <ReadFailed indexers={indexers} rereading={rereading} onReread={onReread} />
  }

  return (
    <>
      {indexers.sites.length > 0 && <AddedSites indexers={indexers} controls={sites} />}
      {/* 既有 Prowlarr 也加得了公開站（M4 票 20）；Berth 不移除它的站。 */}
      <AddSites indexers={indexers} applying={applying} controls={sites} onApply={onApply} />
    </>
  )
}

/** 剖面：這個泊位接上的是哪一台 Prowlarr、加了幾站。 */
function IndexerCutaway({
  indexers,
  service,
  bundled,
}: {
  indexers: IndexerSetup
  service: SetupService | undefined
  bundled: boolean
}) {
  const { t } = useTranslation()

  return (
    <Cutaway title={t('indexer.cutaway.title')}>
      <CutawayRow
        term={t('indexer.cutaway.kind')}
        value={t(bundled ? 'indexer.cutaway.bundled' : 'indexer.cutaway.existing')}
      />
      <CutawayRow term={t('connect.field.baseUrl')} value={indexers.base_url || '—'} />
      <CutawayRow
        term={t('connect.field.apiKey')}
        value={t(keyState(indexers, service))}
        muted={!indexers.api_key_present}
      />
      <CutawayRow
        term={t('indexer.cutaway.added')}
        value={String(indexers.sites.length)}
        muted={indexers.sites.length === 0}
      />
    </Cutaway>
  )
}

/**
 * 右欄的 API key 那一格跟著最近一次連線測試（M4 票 39，審計 s3-14）：連得上才說「已取得」，key 被拒說
 * 不被接受，其餘（連不上、還在等、還沒測）只知道存下了。
 */
function keyState(indexers: IndexerSetup, service: SetupService | undefined) {
  if (!indexers.api_key_present) return 'indexer.cutaway.keyAbsent'
  if (service?.state === 'ok') return 'indexer.cutaway.keyHeld'
  if (service?.reason === 'auth_required') return 'indexer.cutaway.keyRejected'
  return 'indexer.cutaway.keyUnverified'
}

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import type {
  IndexerConnectInput,
  IndexerSetup,
  InterfaceLogin,
  InterfaceLoginRefusal,
  SetupStatus,
} from '../api/setup'
import {
  STICKY_ACTION,
  CopyLine,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
  TEXT_LINK,
} from '../components/controls'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { failureText } from '../components/failures'
import { RequestFailed } from '../components/RequestFailed'
import { StepLine } from '../components/StepLine'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { addressError } from './address'
import { AddedSites, AddSites, type SiteControls } from './IndexerSites'
import { useInterfaceLogin } from './interfaceLogin'
import { BerthLogin } from './InterfaceLoginFields'
import { pointsAtBerth } from './loopback'
import { prowlarrWeb } from './serviceWeb'
import { LoopbackHint, ServiceChoice, type ChoiceControls } from './ServiceChoice'
import type { ChoiceDraft } from './choiceDraft'
import { STEP } from './navigation'
import { GAP, modeOf } from './indexerGaps'
import { VERSION_FLOOR, connected, schemeFix } from './signals'
import { StepFrame } from './StepFrame'

export type { SiteControls } from './IndexerSites'

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
 * - **套件內 Prowlarr**：「已加入」與「加站」兩段（`IndexerSites`），加站旁邊就是「加入 N 個站」；
 *   介面登入是自己的一區與按鈕（`ProwlarrLogin`，M4 票 20），必填。
 * - **既有 Prowlarr**：同樣的「已加入」與「加站」，加的是使用者自己那一台，Berth 不移除（M4 票 20，
 *   使用者拍板：按一次確認）。**一站都沒有時這一頁待處理**（`NoSites`）：到 Prowlarr 加站後重新讀取、
 *   在這裡加推薦的公開站，或之後再說。
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
  applying,
  connecting,
  login,
  onApply,
  onConnect,
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
  applying: boolean
  connecting: boolean
  login: LoginControls
  onApply: (indexers: string[]) => Promise<IndexerSetup>
  onConnect: (input: IndexerConnectInput) => void
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
          <IndexerCutaway indexers={indexers} bundled={mode === 'bundled'} />
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
        existingForm={
          indexers && (
            <ExistingIndexer indexers={indexers} connecting={connecting} onConnect={onConnect} />
          )
        }
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
          <AddSites
            indexers={indexers}
            applying={applying}
            controls={sites}
            onApply={onApply}
            onSkip={onSkip}
            sticky={sticky}
          />
          {mode === 'bundled' && (
            <ProwlarrLogin indexers={indexers} owner={owner} controls={login} />
          )}
        </>
      )}
      {indexersFailed && <p className="mt-6 text-sm text-ink-dim">{t('indexer.unreachable')}</p>}

      {/* 選之前、或讀不到清單時，「之後再說」在這裡；Prowlarr 的在「加入」旁邊。 */}
      {((mode !== 'bundled' && mode !== 'prowlarr') || unread) && (
        <div className="mt-6">
          <GhostButton type="button" busy={applying || connecting} onClick={onSkip}>
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
 * 這一條有結論之前停在頁 4（後端 `_indexer_settled`）。
 */
function ProwlarrLogin({
  indexers,
  owner,
  controls,
}: {
  indexers: IndexerSetup
  owner: string
  controls: LoginControls
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
        <BerthLogin service="prowlarr" current={indexers.web_ui_username} form={form} />
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
      {form.open && (
        <div className="mt-4">
          <PrimaryButton type="button" busy={controls.saving} onClick={save}>
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
 * 這個泊位能做的事：Prowlarr 是已加入 + 加站，既有的另有填位址與 key 的表單。
 * 精靈與設定的索引站那一頁共用這一塊（票 06i）；設定頁不給 `onSkip`——那裡不是第一次，
 * 沒有「之後再說」。介面登入在設定頁它自己的那一區改（M4 票 07）。
 */
export function IndexerActions({
  indexers,
  applying,
  connecting,
  onApply,
  onConnect,
  onSkip,
  sites,
}: {
  indexers: IndexerSetup
  applying: boolean
  connecting: boolean
  onApply: (indexers: string[]) => Promise<IndexerSetup>
  onConnect: (input: IndexerConnectInput) => void
  /** 「之後再說」。只有精靈給。 */
  onSkip?: () => void
  sites: SiteControls
}) {
  const bundled = indexers.origin === 'bundled' && indexers.reachable
  // 連上了：0 站的既有 Prowlarr 是待處理（M4 票 20），也算連上。
  const connected = indexers.steps.some(
    (row) => row.step === 'prowlarr' && row.status !== 'failed' && row.status !== 'running',
  )
  const addSites = (
    <AddSites
      indexers={indexers}
      applying={applying}
      controls={sites}
      onApply={onApply}
      onSkip={onSkip}
    />
  )

  if (bundled) {
    return (
      <>
        {indexers.sites.length > 0 && <AddedSites indexers={indexers} controls={sites} />}
        {addSites}
      </>
    )
  }

  return (
    <>
      {/* 套件內的那台連不上：說清楚，然後照樣給表單——他總得有辦法往下走。 */}
      {indexers.origin === 'bundled' && <Unreachable indexers={indexers} />}
      <ExistingIndexer
        indexers={indexers}
        connecting={connecting}
        onConnect={onConnect}
        onSkip={onSkip}
      />
      {connected && <AddedSites indexers={indexers} controls={sites} />}
      {/* 既有 Prowlarr 也加得了公開站（M4 票 20）；Berth 不移除它的站。 */}
      {connected && indexers.origin === 'existing' && addSites}
    </>
  )
}

/** 剖面：這個泊位接上的是哪一台 Prowlarr、加了幾站。 */
function IndexerCutaway({ indexers, bundled }: { indexers: IndexerSetup; bundled: boolean }) {
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
        value={t(indexers.api_key_present ? 'jellyfin.cutaway.held' : 'jellyfin.cutaway.absent')}
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

/** 既有：Prowlarr 位址 + key，有「測試」。 */
function ExistingIndexer({
  indexers,
  connecting,
  onConnect,
  onSkip,
}: {
  indexers: IndexerSetup
  connecting: boolean
  onConnect: (input: IndexerConnectInput) => void
  /** 設定頁不給；精靈的「之後再說」在頁尾。 */
  onSkip?: () => void
}) {
  const { t } = useTranslation()
  const [baseUrl, setBaseUrl] = useState(indexers.base_url)
  const [apiKey, setApiKey] = useState('')
  const [checked, setChecked] = useState(false)
  // 上一次測試的那一條，只在欄位還是測的那個位址、而且不在測試中時畫（M4 票 21）：換了位址，
  // 它說的就是另一台——狀態列不停在上一次。
  const tested = baseUrl.trim() === indexers.base_url
  const row =
    tested && !connecting ? indexers.steps.find((step) => step.step === 'prowlarr') : undefined

  function submit(event: FormEvent) {
    event.preventDefault()
    setChecked(true)
    if (addressError(t, baseUrl)) return
    onConnect({ base_url: baseUrl.trim(), api_key: apiKey.trim() })
  }

  return (
    <section className="mt-6">
      <h3 className="label text-ink-dim">{t('indexer.existing.title')}</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('indexer.existing.lede')}</p>

      <form onSubmit={submit} noValidate className="mt-4 grid gap-4">
        <Field
          label={t('connect.field.baseUrl')}
          value={baseUrl}
          inputMode="url"
          placeholder="http://192.168.1.10:9696"
          hint={
            <>
              {t('indexer.existing.hint')}
              {pointsAtBerth(baseUrl) && <LoopbackHint />}
            </>
          }
          onChange={(event) => setBaseUrl(event.target.value)}
          error={checked ? addressError(t, baseUrl) : undefined}
        />
        <PasswordField
          label={t('connect.field.apiKey')}
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
        <div className={`grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] ${STICKY_ACTION}`}>
          <PrimaryButton type="submit" busy={connecting}>
            {connecting ? t('indexer.existing.testing') : t('indexer.existing.test')}
          </PrimaryButton>
          {onSkip && (
            <GhostButton type="button" busy={connecting} onClick={onSkip}>
              {t('indexer.skip')}
            </GhostButton>
          )}
        </div>
      </form>

      {row && (
        <ol className="mt-4 grid gap-3" data-testid="sites">
          <StepLine
            label="Prowlarr"
            service="Prowlarr"
            endpoint="GET /api/v1/system/status"
            row={row}
            // 連上了、0 站的待處理不是「尚未執行」（`indexer.existing_prowlarr_step`，M4 票 31）。
            status={row.status === 'pending' ? t('indexer.noSitesYet') : undefined}
            // 照上一次測試的理由與測過的位址（不是欄位裡正在改的那一個）說補法（M4 票 17）。
            fix={existingFix(t, indexers)}
          />
        </ol>
      )}
    </section>
  )
}

/**
 * 既有索引站測不過時的補法：太舊就升級，key 不對就說去哪裡複製（M4 票 20），位址指到 Berth 自己就說
 * localhost，其餘是一般的那一句。
 */
function existingFix(t: TFunction, indexers: IndexerSetup): string {
  if (indexers.reason === 'auth_required') {
    return t('connection.fix.prowlarrKey')
  }
  if (indexers.reason === 'version_unsupported') {
    // 「至少要 X，這一台是 Y」：版本在那一條纜繩的實測值上（`indexer.outdated_step`）。
    const version = indexers.steps.find((row) => row.step === 'prowlarr')?.detail ?? ''
    return t('connection.fix.outdated', { floor: VERSION_FLOOR.prowlarr, version })
  }
  const scheme = schemeFix(indexers.reason)
  if (scheme) return t(scheme)
  if (pointsAtBerth(indexers.base_url)) return t('connect.loopback')
  return t('indexer.existing.fix')
}

/** 連不上套件內的 Prowlarr 時，畫面仍然要說得出下一步。 */
function Unreachable({ indexers }: { indexers: IndexerSetup }) {
  const { t } = useTranslation()

  return (
    <div className="mt-6 grid gap-4">
      <Notice signal="blocked" label={t('common.failed')}>
        {t('indexer.unreachable')}
      </Notice>
      {indexers.error && (
        <p role="alert" className="max-w-prose text-sm text-blocked-ink">
          {failureText(t, indexers, 'Prowlarr')}
        </p>
      )}
      <div className="grid grid-cols-1 gap-px">
        <CopyLine command="docker compose ps prowlarr" />
        <CopyLine command="docker compose logs --tail 50 prowlarr" />
      </div>
      <TechnicalDetails lines={[indexers.base_url, indexers.error]} />
    </div>
  )
}

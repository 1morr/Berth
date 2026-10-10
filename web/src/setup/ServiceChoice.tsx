import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode, type Ref } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import type {
  ChoiceInput,
  ChoiceRefusal,
  ComposeHosts,
  ConnectionReason,
  SetupService,
  SetupStatus,
} from '../api/setup'
import type { ServiceKind, ServiceOrigin } from '../api/schemas'
import {
  CONFIRM_ACTIONS,
  CopyLine,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { RequestFailed } from '../components/RequestFailed'
import { SHARED_ROOT, remedyFor } from '../components/routeChecks'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { escapeOnly } from '../components/useInPlaceConfirm'
import { BAN_DEFAULTS, BAN_WARNING_FROM, SERVICE_LABEL, detailLabel } from '../components/services'
import { SIGNAL_FILL } from '../components/signal'
import { addressError } from './address'
import { LeftoverList } from './LeftoverList'
import type { ChoiceDraft } from './choiceDraft'
import { pointsAtBerth } from './loopback'
import {
  EXAMPLE_ADDRESS,
  REASON_LABEL,
  reasonLabel,
  STATE_LABEL,
  VERSION_FLOOR,
  connectFields,
  connectionField,
  schemeFix,
  bringBack,
  composeProfiles,
  endpointAt,
  signalOf,
  bundledTarget,
  testEndpoint,
  testTarget,
} from './signals'

/**
 * Jellyfin 12.0 的發佈文，TL;DR 那一段就是升級注意：先完整備份、移除第三方插件、升級後完整掃描、
 * 不能降級（brief §20.9）。
 */
const JELLYFIN_UPGRADE_NOTES = 'https://jellyfin.org/posts/jellyfin-release-12.0/#tl-dr'

/** 頁面接到 `ServiceChoice` 的那幾樣：兩支 mutation 與它們的進度（`SetupPage`）。 */
export interface ChoiceControls {
  /**
   * 套件內三個主機名解不解得到（`GET /setup/compose`，M4 票 30）。`false` 的那一個：「套件內」卡片說它沒在跑、
   * 給起回來的兩種補法。沒問到（還在問、問失敗、設定頁）就是空的，不說。
   */
  composeHosts?: ComposeHosts
  /** 選擇送出去還沒回來的那一格；沒有就是 `null`。頁 4 的剖面照它說接法（M4 票 81）。 */
  sending: ServiceOrigin | null
  retesting: boolean
  /**
   * 上一次選擇沒存下的理由（`choiceRefusalOf`）：擁有者成立之後的 Jellyfin 換到另一台（M4 票 18），或
   * 既有服務測不過（`connection_failed`，測過才存，M4 票 45）。表單留著、理由就地說——後者標在欄位上。
   */
  refusal: ChoiceRefusal | null
  /**
   * 選擇或重測的請求本身沒成（不是 `refusal` 那種說得出理由的拒絕）：送不到、422、5xx（M4 票 21）。
   * 原本精靈裡這幾種什麼都不顯示。沒有就是 `null`。
   */
  requestError: unknown
  /** `done`：這一次選擇存下來了才叫——被拒或沒送到時表單留著，改一格再按。 */
  onChoose: (input: ChoiceInput, done?: () => void) => void
  /** `restart`：使用者按的「重新測試」，2 分鐘重新算。 */
  onRetest: (restart: boolean) => void
}

/**
 * 服務頁的頁首：二選一「套件內」/「既有」，選完當場測（plan §9.3〈服務頁的共同形狀〉、
 * `.scratch/m4/service-pages-shape.md`）。
 *
 * **不預選**（shape 時使用者拍板）：猜錯正是 M4 票 15 要消滅的。進頁與選擇之前一個請求都不發；
 * **點**「套件內」就存下並測（唯讀）；點「既有」只展開表單，按「測試連線」才存下並測。
 *
 * **方向鍵只是瀏覽**（M4 票 09，票 15 audit 的 P2）：radio 在兩格間移動就會選中，而選中「套件內」原本
 * 就是一次存下與測試。所以只有指標點下去的那一次算數（方向鍵與空白鍵不送 pointerdown），鍵盤選到的
 * 是草稿，另給一顆「使用套件內的 X」。這一頁已經有結果時換另一格一律先就地確認（`ConfirmPanel`：
 * 焦點進去、Esc 收起回到原本那一格）。
 *
 * **送出的那一刻就有回饋**（M4 票 80）：選擇回來之前，送出去的那一格就是選中的樣子、另一格停用；套件內
 * 第一次選還沒有連線那一列可畫，先畫一條同形的「測試中」（`PendingLine`），回來時換成結果。
 */
export function ServiceChoice({
  kind,
  status,
  composeHosts = {},
  sending,
  retesting,
  refusal,
  requestError,
  locked,
  switchWarning,
  draft,
  onDraft,
  onChoose,
  onRetest,
}: ChoiceControls &
  ChoiceDraft & {
    kind: ServiceKind
    status: SetupStatus
    /** 來源鎖住：擁有者成立之後的 Jellyfin（shape 時拍板）。值是說給人聽的原因。位址照樣改得了。 */
    locked?: string
    /**
     * 這一頁已經有結果時換另一格的後果（這一頁要重做）。有值時換另一格要先確認，確認區列出 Berth 在
     * 原本那一台留下的東西（`LeftoverList`，M4 票 47）。從既有換走時說法不同（`choice.switchAway`）。
     */
    switchWarning?: string
  }) {
  const { t } = useTranslation()
  const choosing = sending !== null
  const groupName = useId()
  const warningId = useId()
  const service = status.services.find((row) => row.kind === kind)
  const [editing, setEditing] = useState(false)
  const [refocusEdit, setRefocusEdit] = useState(false)
  // 既有表單改了一格、還沒按測試：上一次的結果說的是舊的那幾個值，先收起來（M4 票 21）。
  const [edited, setEdited] = useState(false)
  const pointer = useRef(false)
  // 送出去還沒回來的那一格：`choosing` 由真轉假（回來了，成或不成）才清掉。送出與 mutation 進入
  // pending 之間隔一拍，所以不能只看 `choosing`。
  const [sent, setSent] = useState<ServiceOrigin | null>(null)
  const [wasChoosing, setWasChoosing] = useState(choosing)
  if (choosing !== wasChoosing) {
    setWasChoosing(choosing)
    if (!choosing) setSent(null)
  }
  const radios = useRef<Partial<Record<ServiceOrigin, HTMLInputElement | null>>>({})
  const panel = useRef<HTMLDivElement>(null)
  // 點下去開的確認才把焦點送進去；方向鍵瀏覽時焦點留在 radio 上，才走得回另一格。
  const [focusPanel, setFocusPanel] = useState(false)
  const selected = sent ?? draft ?? service?.origin ?? null
  const switching = draft !== null && service !== undefined && draft !== service.origin
  // 這一頁有結果時換另一格：先確認。從既有換走，Berth 沒寫過那一台，說的只有這一頁要重做。
  const confirming = switching && Boolean(switchWarning)
  const warning = service?.origin === 'existing' ? t(`choice.switchAway.${kind}`) : switchWarning
  const name = t(SERVICE_LABEL[kind])
  // 只有 Berth 或容器停了時（M4 票 30、35）：照常列出、不預選、不停用，只說它沒在跑與怎麼起回來。
  const absent = composeHosts[kind] === false

  useEffect(() => {
    if (focusPanel && draft !== null) panel.current?.focus()
  }, [focusPanel, draft])

  /** 送出一個選擇：回來之前那一格就是選中的、另一格停用。 */
  function choose(...args: Parameters<typeof onChoose>) {
    setSent(args[0].origin)
    onChoose(...args)
  }

  function pick(origin: ServiceOrigin) {
    const clicked = pointer.current
    pointer.current = false
    // 請求在路上：不送第二個（M4 票 80）。
    if (locked || sent || choosing) return
    setFocusPanel(false)
    if (origin === service?.origin) {
      onDraft(null)
      // 套件內那一台紅著時再點一次就是重存再測：改了 `.env` 的 port 之後，存下的 compose 位址要換
      // （重新測試只拿存下的那一條再敲一次）。
      if (
        clicked &&
        origin === 'bundled' &&
        !draft &&
        service.state !== 'ok' &&
        service.state !== 'waiting'
      ) {
        choose({ origin: 'bundled' })
      }
      return
    }
    // 第一次點套件內（或換過來而這一頁沒有結果）：直接存下並測。
    if (origin === 'bundled' && clicked && !(service && switchWarning)) {
      onDraft(null)
      choose({ origin: 'bundled' })
      return
    }
    onDraft(origin)
    setFocusPanel(clicked && Boolean(service && switchWarning))
  }

  /** 不換了：回到原本那一格，焦點也回去。 */
  function cancel() {
    onDraft(null)
    setFocusPanel(false)
    const back = service?.origin ?? draft
    if (back) radios.current[back]?.focus()
  }

  function chooseBundled() {
    onDraft(null)
    setFocusPanel(false)
    choose({ origin: 'bundled' })
  }

  function chooseExisting(input: ChoiceInput) {
    setEdited(false)
    // 表單與勾選留到存下來（audit）：先清掉的話，請求還在路上時表單卸下、兩格都沒勾；被拒時
    // （M4 票 18）表單也要留著，理由掛在它上面。
    choose(input, () => {
      onDraft(null)
      setEditing(false)
    })
  }

  // 結果由一直都在的宣告區說（WCAG 4.1.3）：測試那一條跟結果一起掛上，第一次的結果念不出來。
  // 測試中清空、有結果再寫，重測結果一樣也再說一次；啟動中的自動重測不清，免得每 3 秒念一次。
  const testing = choosing || retesting
  // 套件內第一次選（或從既有換過來）：存下的那一列不是這一台，先畫「測試中」。
  const pendingBundled = sent === 'bundled' && service?.origin !== 'bundled'
  const announcement = sent
    ? t(`choice.pending.${sent}`, { service: name })
    : service?.state && !(testing && service.state !== 'waiting')
      ? service.reason
        ? t('connection.announce', {
            service: name,
            state: t(STATE_LABEL[service.state]),
            reason: t(reasonLabel(kind, service.reason, service.state)),
          })
        : `${name} ${t(STATE_LABEL[service.state])}`
      : ''

  // 鎖住的是來源，不是位址：同一個來源換位址照舊可以（設定頁的連線區就是做這件事）。
  const showExistingForm =
    selected === 'existing' && (draft === 'existing' || editing || service?.state !== 'ok')
  const form = showExistingForm && (
    <ExistingForm
      kind={kind}
      status={status}
      service={service?.origin === 'existing' && !edited ? service : undefined}
      initialUrl={service?.origin === 'existing' ? service.base_url : ''}
      inUse={service?.state === 'ok'}
      choosing={choosing}
      refusal={edited ? null : refusal}
      focusFirst={editing}
      onEdit={() => setEdited(true)}
      onSubmit={chooseExisting}
    />
  )
  const cancelButton = (
    <div>
      <GhostButton type="button" onClick={cancel}>
        {t('common.cancel')}
      </GhostButton>
    </div>
  )

  return (
    <section aria-labelledby={`${groupName}-legend`} className="mt-6 grid gap-4">
      <p role="status" data-announcer={kind} className="sr-only">
        {announcement}
      </p>
      {/* 方向鍵瀏覽時焦點留在 radio 上（見上），所以 radio 上的 Esc 也收得起草稿與它的確認。 */}
      <fieldset
        className="grid gap-3"
        onKeyDown={(event) => {
          if (draft !== null && draft !== service?.origin) escapeOnly(event, cancel)
        }}
      >
        <legend id={`${groupName}-legend`} className="label mb-3 text-ink-dim">
          {t('choice.legend', { service: name })}
        </legend>
        {/* 一組選項是這個 fieldset，由 legend 命名；不另掛沒有名字的 `radiogroup`（M4 票 54）。 */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ChoiceCard
            name={groupName}
            origin="bundled"
            checked={selected === 'bundled'}
            disabled={(Boolean(locked) || sent !== null) && selected !== 'bundled'}
            title={t('choice.bundled.title')}
            inputRef={(element) => {
              radios.current.bundled = element
            }}
            onPointer={() => {
              pointer.current = true
            }}
            onPick={pick}
          >
            <span className="block text-xs text-ink-dim">
              {t('choice.bundled.lede', { service: name })}
            </span>
            <span className="value mt-2 block text-xs wrap-anywhere text-ink">
              {status.bundled_targets[kind]}
            </span>
            {/* 中性字、不塗紅：還沒選，不是失敗。 */}
            {absent && (
              <span className="mt-2 block text-xs font-semibold text-ink">
                {t('choice.bundled.absent', { service: name })}
              </span>
            )}
          </ChoiceCard>
          <ChoiceCard
            name={groupName}
            origin="existing"
            checked={selected === 'existing'}
            disabled={(Boolean(locked) || sent !== null) && selected !== 'existing'}
            title={t('choice.existing.title')}
            inputRef={(element) => {
              radios.current.existing = element
            }}
            onPointer={() => {
              pointer.current = true
            }}
            onPick={pick}
          >
            <span className="block text-xs text-ink-dim">
              {t('choice.existing.lede', {
                service: name,
                adds: t(`choice.existing.adds.${kind}`),
              })}
            </span>
            {kind !== 'prowlarr' && (
              <span className="mt-2 block text-xs text-ink">{t('choice.existing.sameHost')}</span>
            )}
            {kind === 'jellyfin' && (
              <span className="mt-2 block text-xs text-ink">{t('choice.existing.library')}</span>
            )}
            {/* 選之前就說出下限（M4 票 17）：版本太舊的那一台要到測試才紅，那時候已經填完表了。 */}
            <span data-testid="version-floor" className="mt-2 block text-xs text-ink">
              {t(`choice.existing.floor.${kind}`)}
              {kind === 'jellyfin' && (
                <>
                  {' '}
                  <a
                    href={JELLYFIN_UPGRADE_NOTES}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="underline underline-offset-2 hover:text-ink-dim"
                  >
                    {t('choice.existing.upgradeNotes')}
                  </a>
                </>
              )}
            </span>
          </ChoiceCard>
        </div>
        {locked && <p className="max-w-prose text-xs text-ink-dim">{locked}</p>}
      </fieldset>

      {/* 選了之後交給測試那一條：套件內是紅的「主機名解不到」與同一組補法，既有是 COMPOSE_PROFILES 那一行
          加停掉已在跑的那一台（只改 profile 再 up -d 停不掉它，brief §20.14）。
          放在卡片外：卡片是一個 label，可複製的那一行有自己的按鈕。 */}
      {absent && selected === null && (
        <div className="grid gap-2">
          <p className="max-w-prose text-xs text-ink-dim">
            {t('choice.bundled.absentFix', { service: name })}
          </p>
          <BringBack status={status} kind={kind} />
        </div>
      )}

      {selected === 'existing' && !locked && (
        <div className="grid gap-2">
          <p className="max-w-prose text-xs text-ink-dim">
            {t('choice.existing.profiles', { kind })}
          </p>
          <CopyLine command={composeProfiles(status, kind, 'existing')} />
          <CopyLine command={`docker compose stop ${kind}`} />
        </div>
      )}

      {draft === 'bundled' && draft !== service?.origin && (
        // 鍵盤選到套件內（還沒送），或這一頁有結果時換成套件內：一顆確認、一顆不換。
        <ConfirmPanel
          panelRef={panel}
          onKeyDown={(event) => escapeOnly(event, cancel)}
          labelledBy={warningId}
        >
          <p id={warningId} className="max-w-prose text-xs text-ink">
            {confirming ? warning : t('choice.useBundledLede', { service: name })}
          </p>
          {confirming && kind !== 'jellyfin' && <LeftoverList kind={kind} />}
          <div className={CONFIRM_ACTIONS}>
            <PrimaryButton type="button" busy={choosing} onClick={chooseBundled}>
              {confirming ? t('choice.switchToBundled') : t('choice.useBundled', { service: name })}
            </PrimaryButton>
            <GhostButton type="button" onClick={cancel}>
              {t('common.cancel')}
            </GhostButton>
          </div>
        </ConfirmPanel>
      )}

      {draft === 'existing' && confirming ? (
        // 這一頁有結果時換成既有：後果、表單（按「測試連線」就是確認）與不換，同一個確認區。
        <ConfirmPanel
          panelRef={panel}
          onKeyDown={(event) => escapeOnly(event, cancel)}
          labelledBy={warningId}
        >
          <p id={warningId} className="max-w-prose text-xs text-ink">
            {warning}
          </p>
          {kind !== 'jellyfin' && <LeftoverList kind={kind} />}
          {form}
          {cancelButton}
        </ConfirmPanel>
      ) : (
        <>
          {form}
          {/* 既有換過去、表單還沒送：留一條退路（票 15 critique：既有表單打開後沒有取消）。 */}
          {switching && draft === 'existing' && cancelButton}
          {/* 「改位址」打開的表單也要能收回去（M4 票 31）：存下的那一台照舊連得上，什麼都不送。 */}
          {editing && !switching && (
            <div>
              <GhostButton
                type="button"
                onClick={() => {
                  setEditing(false)
                  setEdited(false)
                  // 焦點回到「改位址」（DESIGN〈The Focus Follows The Confirm Rule〉）：它要等表單收起、
                  // 測試列重新畫出來才在，所以記一筆，由測試列掛上時接手。
                  setRefocusEdit(true)
                }}
              >
                {t('common.cancel')}
              </GhostButton>
            </div>
          )}
        </>
      )}

      {requestError !== null && requestError !== undefined && (
        // 還沒有擁有者時被要求登入，是擁有者在別處搶先成立了（M4 票 25）：頁 1 選服務、測連線也會撞上。
        <RequestFailed error={requestError} ownerPending={!status.owner} />
      )}

      {pendingBundled && <PendingLine kind={kind} status={status} />}
      {/* 表單改了一格還沒測，上一次的結果說的是舊值，先不畫。 */}
      {service && !switching && !pendingBundled && !(showExistingForm && edited) && (
        <TestLine
          kind={kind}
          status={status}
          service={service}
          testing={testing}
          retesting={retesting}
          onRetest={onRetest}
          onPasteKey={(apiKey) => choose({ origin: 'bundled', api_key: apiKey })}
          onEdit={
            service.origin === 'existing' && !showExistingForm ? () => setEditing(true) : undefined
          }
          editRef={(element: HTMLButtonElement | null) => {
            if (!element || !refocusEdit) return
            element.focus()
            setRefocusEdit(false)
          }}
        />
      )}
    </section>
  )
}

function ChoiceCard({
  name,
  origin,
  checked,
  disabled,
  title,
  inputRef,
  onPointer,
  onPick,
  children,
}: {
  name: string
  origin: ServiceOrigin
  checked: boolean
  disabled: boolean
  title: string
  inputRef: (element: HTMLInputElement | null) => void
  /** 指標按下：接著的那一次選擇是點的，不是方向鍵瀏覽。 */
  onPointer: () => void
  onPick: (origin: ServiceOrigin) => void
  children: ReactNode
}) {
  // 名字只是標題，說明另外念（M4 票 54）：整張卡當名字時「既有」超過 100 字，方向鍵每移一格念一次。
  const cardId = useId()
  return (
    <label
      onPointerDown={onPointer}
      // 選不了的那一格**不加 opacity**（DESIGN〈Chips〉：文字永遠不靠不透明度弱化；實測 2.6:1，M4 票 31
      // 的 audit）：文字照原色，只把底換成頁面底色、拿掉 hover；為什麼選不了，卡片下面那一行（`locked`）說。
      className={`flex min-w-0 gap-3 border-2 px-4 py-3 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--color-working)] ${
        checked
          ? 'cursor-pointer border-rule-strong bg-deck'
          : disabled
            ? 'cursor-not-allowed border-rule bg-hull'
            : 'cursor-pointer border-rule bg-well hover:border-rule-strong'
      }`}
    >
      <input
        ref={inputRef}
        type="radio"
        name={name}
        value={origin}
        checked={checked}
        disabled={disabled}
        // 點同一格也要收到：換過另一格又取消之後，再點回原本那一格是「不換了」。
        onChange={() => onPick(origin)}
        onClick={() => checked && onPick(origin)}
        aria-labelledby={`${cardId}-title`}
        aria-describedby={`${cardId}-body`}
        className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)]"
      />
      <span className="min-w-0">
        <span id={`${cardId}-title`} className="block text-sm font-semibold text-ink">
          {title}
        </span>
        <span id={`${cardId}-body`} className="block">
          {children}
        </span>
      </span>
    </label>
  )
}

/**
 * 選「既有」的表單：位址 + 那個服務要的憑證（brief §16.4）。**測過才存**（M4 票 45）：測不過的那一次
 * 什麼都不存，結論（`refusal.attempt`）標在欄位上——位址錯標位址、憑證錯標憑證（`connectionField`），
 * 其餘在表單裡、送出鍵上面；技術細節收在最後（票 21 的分層）。改一格再按靠的是欄位留著打的字。
 * 擁有者成立之後的 Jellyfin 換到另一台也不存（M4 票 18），那一句照舊在表單裡。
 */
export function ExistingForm({
  kind,
  status,
  service,
  initialUrl,
  inUse,
  choosing,
  refusal,
  focusFirst,
  onEdit,
  onSubmit,
}: {
  kind: ServiceKind
  status: SetupStatus
  /** 存下的那一份（重新測試被拒時，連錯的次數在它上面）。改了一格之後是 `undefined`：它說的是舊值。 */
  service: SetupService | undefined
  /** 已經選過既有的話，位址帶回來，不必重打。 */
  initialUrl: string
  /** 已經有一台連得上的在用：測不過時說它照舊在用。 */
  inUse: boolean
  choosing: boolean
  refusal: ChoiceRefusal | null
  /** 按「改位址或憑證」打開的：那顆鈕自己卸下了，焦點交給位址欄（audit）。 */
  focusFirst: boolean
  /** 任何一格改了：上一次的結果與拒絕不再對得上這些值。 */
  onEdit: () => void
  onSubmit: (input: ChoiceInput) => void
}) {
  const { t } = useTranslation()
  const [baseUrl, setBaseUrl] = useState(initialUrl)
  const [apiKey, setApiKey] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [checked, setChecked] = useState(false)
  const fields = connectFields(kind)
  const credentialError = useId()
  // 測不過的那一次（沒存下）：標在哪一格、那一句人話（與連線卡的補法同一句）。
  const attempt = refusal?.reason === 'connection_failed' ? (refusal.attempt ?? null) : null
  const field = attempt?.reason ? connectionField(kind, attempt.reason) : null
  const { lede: said, remedy } = attempt
    ? fixOf(t, kind, status, attempt)
    : { lede: undefined, remedy: null }
  const typed = checked ? addressError(t, baseUrl) : undefined

  function submit(event: FormEvent) {
    event.preventDefault()
    setChecked(true)
    if (addressError(t, baseUrl)) return
    onSubmit({
      origin: 'existing',
      base_url: baseUrl.trim(),
      api_key: apiKey.trim(),
      username,
      password,
    })
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid gap-4 border-2 border-rule-strong bg-hull px-4 py-4"
    >
      <p className="max-w-prose text-xs text-ink-dim">{t(`connect.hint.${kind}`)}</p>
      {kind === 'qbittorrent' && (
        // 測試會放一個探針（M4 票 46）。說法沿用頁 3「按下之後會」（M4 票 19、31）：只有使用者自己那一台
        // 可能設了執行外部程式，套件內不提。
        <p className="-mt-2 max-w-prose text-xs text-ink-dim">
          {t('connect.probe', { root: SHARED_ROOT })}
        </p>
      )}
      <Field
        label={t('connect.field.baseUrl')}
        value={baseUrl}
        inputMode="url"
        autoFocus={focusFirst}
        placeholder={EXAMPLE_ADDRESS[kind]}
        hint={pointsAtBerth(baseUrl) ? <LoopbackHint /> : undefined}
        onChange={(event) => {
          setBaseUrl(event.target.value)
          onEdit()
        }}
        error={typed ?? (field === 'address' ? said : undefined)}
      />
      {fields.includes('apiKey') && (
        <PasswordField
          label={t('connect.field.apiKey')}
          value={apiKey}
          autoComplete="off"
          error={field === 'credentials' ? said : undefined}
          onChange={(event) => {
            setApiKey(event.target.value)
            onEdit()
          }}
        />
      )}
      {fields.includes('credentials') && (
        <>
          {/* 帳密錯是兩格的事：兩格都標，那一句寫一次、兩格都指到它（M4 票 45）。 */}
          <Field
            label={t('connect.field.username')}
            value={username}
            autoComplete="off"
            invalid={field === 'credentials'}
            describedBy={field === 'credentials' ? credentialError : undefined}
            onChange={(event) => {
              setUsername(event.target.value)
              onEdit()
            }}
          />
          <PasswordField
            label={t('connect.field.password')}
            value={password}
            autoComplete="off"
            hint={banWarning(t, attempt ?? service)}
            invalid={field === 'credentials'}
            describedBy={field === 'credentials' ? credentialError : undefined}
            onChange={(event) => {
              setPassword(event.target.value)
              onEdit()
            }}
          />
          {field === 'credentials' && (
            <span id={credentialError} role="alert" className="-mt-2 text-xs text-blocked-ink">
              {said}
            </span>
          )}
        </>
      )}
      {attempt && field === null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {said}
          {/* 看不到 /data 時那一台要多加的掛載（M4 票 46）；其餘不屬於哪一格的沒有片段。 */}
          {remedy && <div className="mt-2">{remedy}</div>}
        </Notice>
      )}
      {attempt && (
        <div className="grid gap-1">
          <p className="max-w-prose text-xs text-ink-dim">
            {t(inUse ? 'connect.notSavedInUse' : 'connect.notSaved')}
          </p>
          <TechnicalDetails lines={[endpointAt(attempt.base_url, kind), attempt.error]} />
        </div>
      )}
      {refusal && refusal.reason !== 'connection_failed' && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t(`choice.refused.${refusal.reason}`, {
            detail: refusedDetail(refusal, t),
          })}
        </Notice>
      )}
      <div>
        <PrimaryButton type="submit" busy={choosing}>
          {choosing ? t('connect.submitting') : t('connect.submit')}
        </PrimaryButton>
      </div>
    </form>
  )
}

/**
 * 連錯的預警（M4 票 21）：第 3 次起在密碼欄下說「再錯 N 次會被封」。只提示、不擋按鈕；被封之後是
 * 測試那一條的紅燈（`connection.fix.banned`）。次數是 Berth 自己數的，所以是「至少」——qBittorrent 數的是
 * 這台的 IP，別的程式用錯的帳密連它也算。
 */
function banWarning(t: TFunction, service: SetupService | undefined): string | undefined {
  if (!service || service.kind !== 'qbittorrent' || service.reason !== 'auth_required') return
  const failures = service.auth_failures
  const left = BAN_DEFAULTS.limit - failures
  if (failures < BAN_WARNING_FROM) return
  if (left <= 0) return t('connection.fix.authWarningLast', { failures, ...BAN_DEFAULTS })
  return t('connection.fix.authWarning', { failures, left, ...BAN_DEFAULTS })
}

/** 拒絕的細節：認不出是哪一台時是那一次測試的理由，照 UI 語言說；另一台時是它的伺服器名。 */
function refusedDetail(refusal: ChoiceRefusal, t: TFunction): string {
  const reason = refusal.detail as ConnectionReason
  return refusal.reason === 'unverified' && reason in REASON_LABEL
    ? t(REASON_LABEL[reason])
    : refusal.detail
}

/**
 * 既有服務的位址指到 Berth 自己（`pointsAtBerth`）時，位址欄下的那一句（M4 票 17）。只提示、不擋：
 * `network_mode: host` 的部署填 localhost 是對的。呼叫端先判斷，這裡只畫。
 */
export function LoopbackHint() {
  const { t } = useTranslation()
  return (
    <span
      data-testid="loopback-hint"
      className="mt-1 block border-l-2 border-assigned pl-2 text-ink"
    >
      {t('connect.loopback')}
    </span>
  )
}

/**
 * 選了套件內、還沒回來（M4 票 80）：與 `TestLine` 同一個框與行首，回來時同一個位置換成結果。宣告由
 * `ServiceChoice` 那一個宣告區說，這裡不另開。
 */
function PendingLine({ kind, status }: { kind: ServiceKind; status: SetupStatus }) {
  const { t } = useTranslation()
  const name = t(SERVICE_LABEL[kind])

  return (
    <div className="min-w-0 border-2 border-rule bg-well">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL.working}`}>
          {t('connection.testing')}
        </span>
        <span className="value text-sm font-semibold text-ink">{name}</span>
        <span className="value min-w-0 text-xs wrap-anywhere text-ink-dim">
          {bundledTarget(status, kind)}
        </span>
      </div>
      <p className="border-t-2 border-rule px-4 py-3 text-sm text-ink">
        {t('choice.pending.bundled', { service: name })}
      </p>
    </div>
  )
}

/**
 * 測試那一條：信號、服務、連哪裡、結果與實測值。紅燈就地說出補法（PRODUCT.md 原則 4），
 * 「重新測試」只在出問題的這一條上（取代原本的「重新偵測這個服務」）。
 */
export function TestLine({
  kind,
  status,
  service,
  testing,
  retesting,
  onRetest,
  onPasteKey,
  onEdit,
  editRef,
}: {
  kind: ServiceKind
  status: SetupStatus
  service: SetupService
  testing: boolean
  retesting: boolean
  onRetest: (restart: boolean) => void
  /** 套件內 Prowlarr 讀不到掛載的 key：就地貼上（plan §9.2）。 */
  onPasteKey?: (apiKey: string) => void
  /** 既有而連上了：再打開表單改位址或憑證。 */
  onEdit?: () => void
  /** 「改位址」那顆鍵。表單收起時焦點要回到它。 */
  editRef?: Ref<HTMLButtonElement>
}) {
  const { t } = useTranslation()
  const state = service.state
  const signal = testing && state !== 'waiting' ? 'working' : signalOf(service)
  const failed = state === 'failed' || state === 'timeout'

  return (
    <div className="min-w-0 border-2 border-rule bg-well">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[signal]}`}>
          {testing && state !== 'waiting'
            ? t('connection.testing')
            : state
              ? t(STATE_LABEL[state])
              : t('connection.untested')}
        </span>
        <span className="value text-sm font-semibold text-ink">{t(SERVICE_LABEL[kind])}</span>
        <span className="value min-w-0 text-xs wrap-anywhere text-ink-dim">
          {testTarget(status, kind)}
        </span>
        {!failed && !testing && (
          <TechnicalDetails inline lines={[testEndpoint(status, kind), service.error]} />
        )}
      </div>

      {/* 測試中不畫上一次的結果：它說的是這一次之前的那一台（M4 票 21）。 */}
      {service.reason && !testing && (
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 border-t-2 border-rule px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <dt className="label self-center text-ink-dim">{t('connection.result')}</dt>
          <dd className="text-sm text-ink">{t(reasonLabel(kind, service.reason, state))}</dd>
          {service.detail && (
            <>
              <dt className="label mt-1 self-center text-ink-dim">
                {t(detailLabel(kind, service.reason))}
              </dt>
              <dd className="value mt-1 text-sm text-ink">{service.detail}</dd>
            </>
          )}
          {state === 'waiting' && (
            <>
              {/* 倒數貼在還在等的那一條上：它說的就是這個服務。 */}
              <dt className="label mt-1 self-center text-ink-dim">
                {t('connection.waitingLabel')}
              </dt>
              <dd className="mt-1 text-sm text-ink">
                <span className="value">
                  {t('connection.waiting', {
                    waited: service.waited_seconds,
                    window: status.window_seconds,
                  })}
                </span>
                <span className="mt-1 block text-xs text-ink-dim">
                  {t('connection.waitingHint')}
                </span>
              </dd>
            </>
          )}
        </dl>
      )}

      {failed && !testing && <Fix kind={kind} status={status} service={service} />}

      {service.origin === 'bundled' && service.reason === 'api_key_missing' && onPasteKey && (
        <PasteKey choosing={testing} onPaste={onPasteKey} />
      )}

      {(failed || onEdit) && (
        <div className="flex flex-wrap gap-3 border-t-2 border-rule px-4 py-3">
          {failed && (
            <GhostButton type="button" busy={retesting} onClick={() => onRetest(true)}>
              {retesting ? t('connection.retesting') : t('connection.retest')}
            </GhostButton>
          )}
          {onEdit && (
            // Jellyfin 沒有憑證欄（管理員帳密在擁有者表單），它那一格只改位址（M4 票 18）。
            <GhostButton ref={editRef} type="button" onClick={onEdit}>
              {kind === 'jellyfin' ? t('connection.editAddress') : t('connection.edit')}
            </GhostButton>
          )}
        </div>
      )}
    </div>
  )
}

/** 紅燈的補法。套件內與既有的下一步不同：前者是 compose，後者是使用者自己的那一台。 */
export function Fix({
  kind,
  status,
  service,
}: {
  kind: ServiceKind
  status: SetupStatus
  service: SetupService
}) {
  const { t } = useTranslation()
  const { lede, remedy } = fixOf(t, kind, status, service)

  return (
    <section className="border-t-2 border-rule px-4 py-3">
      <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
      <p className="mt-2 max-w-prose text-xs text-ink-dim">{lede}</p>
      {remedy && <div className="mt-2">{remedy}</div>}
      <TechnicalDetails lines={[testEndpoint(status, kind), service.error]} />
    </section>
  )
}

/**
 * 補法的那一句人話與它下面可複製的指令（沒有就是 `null`）。連線卡的紅燈與既有表單測不過時標在欄位上
 * 的那一句（M4 票 45）是同一句。
 */
function fixOf(
  t: TFunction,
  kind: ServiceKind,
  status: SetupStatus,
  service: SetupService,
): { lede: string; remedy: ReactNode } {
  const bundled = service.origin === 'bundled'
  const reason = service.reason

  let lede: string
  // lede 下面那一塊：可複製的指令（沒有就不畫）。
  let remedy: ReactNode = null
  // 「至少要 X，這一台是 Y」（M4 票 18）：與「既有」旁的下限同一組數字。
  const outdated = { floor: VERSION_FLOOR[kind], version: service.detail }
  const scheme = schemeFix(reason)
  if (kind === 'jellyfin' && reason === 'auth_required') {
    // 同一台、Berth 的 key 被撤了：套件內或既有都一樣，擁有者重新登入換一把（M4 票 18）。
    lede = t('connection.fix.jellyfinKey')
  } else if (reason === 'other_server') {
    // 不提它的名字：新開的 Jellyfin 伺服器名預設是主機名，在容器裡就是容器 ID，使用者認不出來
    // （M4 票 31）。名字留在下面「伺服器」那一格與技術細節。
    lede = t('connection.fix.otherServer')
  } else if (scheme) {
    // 位址的協定寫錯（M4 票 25）：原本說成連不上、叫人查 port。
    lede = t(scheme)
  } else if (reason === 'data_unseen') {
    // 頁 2 就問看不看得到 /data（M4 票 46）。片段是頁 3 `download_visible` 那一組（`remedyFor`）：既有的
    // 只多加一條、compose 與 docker run 各一（M4 票 36），套件內的與 deploy 的 compose 一字不差。路徑是
    // 後端放探測檔的那一個（`detail`），不寫死。
    const fix = remedyFor('download_visible', {
      existing: { qbittorrent: !bundled, jellyfin: false, root: service.detail || SHARED_ROOT },
      crossDevice: false,
    })
    lede = t(bundled ? 'connection.fix.dataUnseenBundled' : 'connection.fix.dataUnseen', {
      root: fix.root,
    })
    remedy = <CopyLines commands={[...fix.commands]} />
  } else if (reason === 'data_unreadable') {
    lede = t('connection.fix.dataUnreadable', { root: service.detail || SHARED_ROOT })
  } else if (reason === 'data_unsettled') {
    lede = t('connection.fix.dataUnsettled')
  } else if (bundled && reason === 'not_deployed') {
    // 主機名解不到＝容器停了或不在 COMPOSE_PROFILES 裡：兩種起回來的方法都給（plan §9.3、M4 票 35）。
    lede = t('connection.fix.notDeployed', { kind })
    remedy = <BringBack status={status} kind={kind} />
  } else if (bundled && reason === 'protocol_mismatch') {
    lede = t('connection.fix.somethingElse', { kind })
  } else if (bundled && reason === 'api_key_missing') {
    lede = t('connection.fix.apiKeyMissing')
  } else if (bundled && kind === 'prowlarr' && reason === 'auth_required') {
    // Prowlarr 不靠白名單：Berth 讀掛載的 key，每次重新測試都重讀（M4 票 27）。key 被重新產生過、
    // 掛載卻沒進來時，說的是掛載。
    lede = t('connection.fix.prowlarrMount')
  } else if (bundled && reason === 'auth_required') {
    // 補法在 WebUI：預置腳本缺鍵才補，重啟補不回使用者關掉的白名單（M4 票 53）。
    lede = t('connection.fix.whitelist')
  } else if (bundled && reason === 'version_unsupported') {
    lede = t('connection.fix.outdatedBundled', outdated)
    remedy = (
      <CopyLines commands={[`docker compose pull ${kind}`, `docker compose up -d ${kind}`]} />
    )
  } else if (bundled) {
    lede = t('connection.fix.bundledDown')
    remedy = (
      <CopyLines
        commands={[`docker compose ps ${kind}`, `docker compose logs --tail 50 ${kind}`]}
      />
    )
  } else if (kind === 'prowlarr' && reason === 'auth_required') {
    // Prowlarr 只有 key，沒有帳密：說去哪裡複製、不是介面登入的密碼（M4 票 20；頁 4 原本自己那一份的這一句，
    // 票 39 起由這裡說）。
    lede = t('connection.fix.prowlarrKey')
  } else if (reason === 'auth_required') {
    lede = t('connection.fix.credentials')
  } else if (reason === 'api_key_missing') {
    // 既有 Prowlarr 的 key 留空（M4 票 39 的 code-review）：Berth 先問到它在，才說缺 key。
    lede = t('connection.fix.apiKeyEmpty')
  } else if (reason === 'ip_banned') {
    lede = t('connection.fix.banned', BAN_DEFAULTS)
  } else if (reason === 'version_unsupported') {
    lede = t('connection.fix.outdated', outdated)
  } else if (pointsAtBerth(service.base_url)) {
    // 位址欄下的那一句（M4 票 17）：填 localhost 的人最常卡在這裡，而「連不上」看不出原因。
    lede = t('connect.loopback')
  } else {
    lede = t('connection.fix.address')
  }
  return { lede, remedy }
}

/** 一組可複製的指令，一行一條。 */
function CopyLines({ commands }: { commands: string[] }) {
  return (
    <div className="grid grid-cols-1 gap-px">
      {commands.map((command) => (
        <CopyLine key={command} command={command} />
      ))}
    </div>
  )
}

/** 套件內那一台主機名解不到時的兩種補法（`bringBack`）：各自一句什麼情況、底下是可複製的指令。 */
function BringBack({ status, kind }: { status: SetupStatus; kind: ServiceKind }) {
  const { t } = useTranslation()
  const { stopped, missing } = bringBack(status, kind)
  return (
    <div className="grid gap-3">
      <div className="grid gap-1">
        <p className="max-w-prose text-xs text-ink-dim">{t('choice.bringBack.stopped')}</p>
        <CopyLines commands={stopped} />
      </div>
      <div className="grid gap-1">
        <p className="max-w-prose text-xs text-ink-dim">
          {t('choice.bringBack.missing', { kind })}
        </p>
        <CopyLines commands={missing} />
      </div>
    </div>
  )
}

function PasteKey({ choosing, onPaste }: { choosing: boolean; onPaste: (apiKey: string) => void }) {
  const { t } = useTranslation()
  const [apiKey, setApiKey] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (apiKey.trim()) onPaste(apiKey.trim())
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-3 border-t-2 border-rule px-4 py-3">
      <PasswordField
        label={t('connect.field.apiKey')}
        value={apiKey}
        autoComplete="off"
        onChange={(event) => setApiKey(event.target.value)}
      />
      <div>
        <GhostButton type="submit" busy={choosing}>
          {t('connection.pasteKey')}
        </GhostButton>
      </div>
    </form>
  )
}

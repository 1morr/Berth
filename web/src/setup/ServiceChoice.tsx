import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import type {
  ChoiceInput,
  ChoiceRefusal,
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
import { escapeOnly } from '../components/useInPlaceConfirm'
import { SERVICE_LABEL, detailLabel } from '../components/services'
import { SIGNAL_FILL } from '../components/signal'
import type { ChoiceDraft } from './choiceDraft'
import { pointsAtBerth } from './loopback'
import {
  EXAMPLE_ADDRESS,
  REASON_LABEL,
  STATE_LABEL,
  VERSION_FLOOR,
  connectFields,
  composeProfiles,
  signalOf,
  testEndpoint,
} from './signals'

/**
 * Jellyfin 12.0 的發佈文，TL;DR 那一段就是升級注意：先完整備份、移除第三方插件、升級後完整掃描、
 * 不能降級（brief §20.9）。
 */
const JELLYFIN_UPGRADE_NOTES = 'https://jellyfin.org/posts/jellyfin-release-12.0/#tl-dr'

/** 頁面接到 `ServiceChoice` 的那幾樣：兩支 mutation 與它們的進度（`SetupPage`）。 */
export interface ChoiceControls {
  /** 選擇送出去還沒回來。 */
  choosing: boolean
  retesting: boolean
  /**
   * 上一次選擇沒存下的理由（`choiceRefusalOf`，409）：擁有者成立之後的 Jellyfin 換到另一台、或新位址
   * 認不出是哪一台（M4 票 18）。表單留著、理由就地說。
   */
  refusal: ChoiceRefusal | null
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
 */
export function ServiceChoice({
  kind,
  status,
  choosing,
  retesting,
  refusal,
  locked,
  switchWarning,
  existingForm,
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
     * 這一頁已經有結果時換另一格的後果（Berth 寫進原本那一台的東西不撤回、這一頁要重做）。
     * 有值時換另一格要先確認。從既有換走時說法不同：Berth 沒寫過使用者那一台（`choice.switchAway`）。
     */
    switchWarning?: string
    /** 既有那一格自己的表單（Prowlarr 頁：Prowlarr 或 Torznab）。沒給就是內建的位址與憑證。 */
    existingForm?: ReactNode
  }) {
  const { t } = useTranslation()
  const groupName = useId()
  const warningId = useId()
  const service = status.services.find((row) => row.kind === kind)
  const [editing, setEditing] = useState(false)
  const pointer = useRef(false)
  const radios = useRef<Partial<Record<ServiceOrigin, HTMLInputElement | null>>>({})
  const panel = useRef<HTMLDivElement>(null)
  // 點下去開的確認才把焦點送進去；方向鍵瀏覽時焦點留在 radio 上，才走得回另一格。
  const [focusPanel, setFocusPanel] = useState(false)
  const selected = draft ?? service?.origin ?? null
  const switching = draft !== null && service !== undefined && draft !== service.origin
  // 這一頁有結果時換另一格：先確認。從既有換走，Berth 沒寫過那一台，說的只有這一頁要重做。
  const confirming = switching && Boolean(switchWarning)
  const warning = service?.origin === 'existing' ? t(`choice.switchAway.${kind}`) : switchWarning
  const name = t(SERVICE_LABEL[kind])

  useEffect(() => {
    if (focusPanel && draft !== null) panel.current?.focus()
  }, [focusPanel, draft])

  function pick(origin: ServiceOrigin) {
    const clicked = pointer.current
    pointer.current = false
    if (locked) return
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
        onChoose({ origin: 'bundled' })
      }
      return
    }
    // 第一次點套件內（或換過來而這一頁沒有結果）：直接存下並測。
    if (origin === 'bundled' && clicked && !(service && switchWarning)) {
      onDraft(null)
      onChoose({ origin: 'bundled' })
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
    onChoose({ origin: 'bundled' })
  }

  function chooseExisting(input: ChoiceInput) {
    // 表單與勾選留到存下來（audit）：先清掉的話，請求還在路上時表單卸下、兩格都沒勾；被拒時
    // （M4 票 18）表單也要留著，理由掛在它上面。
    onChoose(input, () => {
      onDraft(null)
      setEditing(false)
    })
  }

  // 結果由一直都在的宣告區說（WCAG 4.1.3）：測試那一條跟結果一起掛上，第一次的結果念不出來。
  // 測試中清空、有結果再寫，重測結果一樣也再說一次；啟動中的自動重測不清，免得每 3 秒念一次。
  const testing = choosing || retesting
  const announcement =
    service?.state && !(testing && service.state !== 'waiting')
      ? service.reason
        ? t('connection.announce', {
            service: name,
            state: t(STATE_LABEL[service.state]),
            reason: t(REASON_LABEL[service.reason]),
          })
        : `${name} ${t(STATE_LABEL[service.state])}`
      : ''

  // 鎖住的是來源，不是位址：同一個來源換位址照舊可以（設定頁的連線區就是做這件事）。
  const showExistingForm =
    selected === 'existing' && (draft === 'existing' || editing || service?.state !== 'ok')
  const form =
    showExistingForm &&
    (existingForm ?? (
      <ExistingForm
        kind={kind}
        service={service?.origin === 'existing' ? service : undefined}
        choosing={choosing}
        refusal={refusal}
        focusFirst={editing}
        onSubmit={chooseExisting}
      />
    ))
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
        <div role="radiogroup" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ChoiceCard
            name={groupName}
            origin="bundled"
            checked={selected === 'bundled'}
            disabled={Boolean(locked) && selected !== 'bundled'}
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
          </ChoiceCard>
          <ChoiceCard
            name={groupName}
            origin="existing"
            checked={selected === 'existing'}
            disabled={Boolean(locked) && selected !== 'existing'}
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
              {t('choice.existing.lede', { service: name })}
            </span>
            {kind !== 'prowlarr' && (
              <span className="mt-2 block text-xs text-ink">{t('choice.existing.sameHost')}</span>
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

      {selected === 'existing' && !locked && (
        <div className="grid gap-2">
          <p className="max-w-prose text-xs text-ink-dim">
            {t('choice.existing.profiles', { kind })}
          </p>
          <CopyLine command={composeProfiles(status, kind, 'existing')} />
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
          {form}
          {cancelButton}
        </ConfirmPanel>
      ) : (
        <>
          {form}
          {/* 既有換過去、表單還沒送：留一條退路（票 15 critique：既有表單打開後沒有取消）。 */}
          {switching && draft === 'existing' && cancelButton}
        </>
      )}

      {/* 自己帶表單的那一種（Prowlarr 頁的既有）在表單下面說結果，這一條就不重複。 */}
      {service && !switching && !(showExistingForm && existingForm) && (
        <TestLine
          kind={kind}
          status={status}
          service={service}
          testing={testing}
          retesting={retesting}
          onRetest={onRetest}
          onPasteKey={(apiKey) => onChoose({ origin: 'bundled', api_key: apiKey })}
          onEdit={
            service.origin === 'existing' && !showExistingForm ? () => setEditing(true) : undefined
          }
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
  return (
    <label
      onPointerDown={onPointer}
      className={`flex min-w-0 cursor-pointer gap-3 border-2 px-4 py-3 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--color-working)] ${
        checked ? 'border-rule-strong bg-deck' : 'border-rule bg-well hover:border-rule-strong'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
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
        className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)]"
      />
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        {children}
      </span>
    </label>
  )
}

/**
 * 選「既有」的表單：位址 + 那個服務要的憑證（brief §16.4）。測不過也存，改一格再按；擁有者成立之後的
 * Jellyfin 換到另一台不存（`refusal`，M4 票 18）。
 */
function ExistingForm({
  kind,
  service,
  choosing,
  refusal,
  focusFirst,
  onSubmit,
}: {
  kind: ServiceKind
  /** 已經選過既有的那一份：位址帶回來，不必重打。 */
  service: SetupService | undefined
  choosing: boolean
  refusal: ChoiceRefusal | null
  /** 按「改位址或憑證」打開的：那顆鈕自己卸下了，焦點交給位址欄（audit）。 */
  focusFirst: boolean
  onSubmit: (input: ChoiceInput) => void
}) {
  const { t } = useTranslation()
  const [baseUrl, setBaseUrl] = useState(service?.base_url ?? '')
  const [apiKey, setApiKey] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [checked, setChecked] = useState(false)
  const fields = connectFields(kind)

  function submit(event: FormEvent) {
    event.preventDefault()
    setChecked(true)
    if (!baseUrl.trim()) return
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
      <Field
        label={t('connect.field.baseUrl')}
        value={baseUrl}
        inputMode="url"
        autoFocus={focusFirst}
        placeholder={EXAMPLE_ADDRESS[kind]}
        hint={pointsAtBerth(baseUrl) ? <LoopbackHint /> : undefined}
        onChange={(event) => setBaseUrl(event.target.value)}
        error={checked && !baseUrl.trim() ? t('connect.error.blank') : undefined}
      />
      {fields.includes('apiKey') && (
        <PasswordField
          label={t('connect.field.apiKey')}
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
      )}
      {fields.includes('credentials') && (
        <>
          <Field
            label={t('connect.field.username')}
            value={username}
            autoComplete="off"
            onChange={(event) => setUsername(event.target.value)}
          />
          <PasswordField
            label={t('connect.field.password')}
            value={password}
            autoComplete="off"
            onChange={(event) => setPassword(event.target.value)}
          />
        </>
      )}
      {refusal && (
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
        <span className="value ml-auto min-w-0 truncate text-xs text-ink-dim">
          {testEndpoint(status, kind)}
        </span>
      </div>

      {service.reason && (
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 border-t-2 border-rule px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <dt className="label self-center text-ink-dim">{t('connection.result')}</dt>
          <dd className="text-sm text-ink">{t(REASON_LABEL[service.reason])}</dd>
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

      {failed && <Fix kind={kind} status={status} service={service} />}

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
            <GhostButton type="button" onClick={onEdit}>
              {kind === 'jellyfin' ? t('connection.editAddress') : t('connection.edit')}
            </GhostButton>
          )}
        </div>
      )}
    </div>
  )
}

/** 紅燈的補法。套件內與既有的下一步不同：前者是 compose，後者是使用者自己的那一台。 */
function Fix({
  kind,
  status,
  service,
}: {
  kind: ServiceKind
  status: SetupStatus
  service: SetupService
}) {
  const { t } = useTranslation()
  const bundled = service.origin === 'bundled'
  const reason = service.reason

  let lede: string
  let commands: string[] = []
  // 「至少要 X，這一台是 Y」（M4 票 18）：與「既有」旁的下限同一組數字。
  const outdated = { floor: VERSION_FLOOR[kind], version: service.detail }
  if (kind === 'jellyfin' && reason === 'auth_required') {
    // 同一台、Berth 的 key 被撤了：套件內或既有都一樣，擁有者重新登入換一把（M4 票 18）。
    lede = t('connection.fix.jellyfinKey')
  } else if (reason === 'other_server') {
    lede = t('connection.fix.otherServer', { name: service.detail })
  } else if (bundled && reason === 'not_deployed') {
    // 主機名解不到＝它不在 compose 裡：說出怎麼加回來（plan §9.3）。
    lede = t('connection.fix.notDeployed', { kind })
    commands = [composeProfiles(status, kind, 'bundled'), 'docker compose up -d']
  } else if (bundled && reason === 'protocol_mismatch') {
    lede = t('connection.fix.somethingElse', { kind })
  } else if (bundled && reason === 'api_key_missing') {
    lede = t('connection.fix.apiKeyMissing')
  } else if (bundled && reason === 'auth_required') {
    lede = t('connection.fix.whitelist')
    commands = [`docker compose restart ${kind}`]
  } else if (bundled && reason === 'version_unsupported') {
    lede = t('connection.fix.outdatedBundled', outdated)
    commands = [`docker compose pull ${kind}`, `docker compose up -d ${kind}`]
  } else if (bundled) {
    lede = t('connection.fix.bundledDown')
    commands = [`docker compose ps ${kind}`, `docker compose logs --tail 50 ${kind}`]
  } else if (reason === 'auth_required') {
    lede = t('connection.fix.credentials')
  } else if (reason === 'ip_banned') {
    lede = t('connection.fix.banned')
  } else if (reason === 'version_unsupported') {
    lede = t('connection.fix.outdated', outdated)
  } else if (pointsAtBerth(service.base_url)) {
    // 位址欄下的那一句（M4 票 17）：填 localhost 的人最常卡在這裡，而「連不上」看不出原因。
    lede = t('connect.loopback')
  } else {
    lede = t('connection.fix.address')
  }

  return (
    <section className="border-t-2 border-rule px-4 py-3">
      <h5 className="label text-ink-dim">{t('connect.fix.title')}</h5>
      <p className="mt-2 max-w-prose text-xs text-ink-dim">{lede}</p>
      {commands.length > 0 && (
        <div className="mt-2 grid grid-cols-1 gap-px">
          {commands.map((command) => (
            <CopyLine key={command} command={command} />
          ))}
        </div>
      )}
    </section>
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

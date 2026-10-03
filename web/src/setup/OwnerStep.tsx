import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  JellyfinConnectInput,
  OwnerInput,
  OwnerRefusal,
  SetupService,
  SetupStatus,
} from '../api/setup'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { ORIGIN_LABEL } from '../components/services'
import {
  STICKY_ACTION,
  Checkbox,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { JellyfinSignInForm } from './JellyfinExisting'
import { JELLYFIN_LOCALES, localeForUi, localeLabel } from './jellyfinStartup'
import { ServiceChoice, type ChoiceControls } from './ServiceChoice'
import type { ChoiceDraft } from './choiceDraft'
import { connected } from './signals'
import { StepFrame } from './StepFrame'

/** 擁有者成立之後 Berth 的 key 被撤了：就地重新登入換一把（M4 票 18）。 */
export interface ReSignIn {
  connecting: boolean
  /** 沒送到，或 Jellyfin 那一段沒換到 key。 */
  failed: boolean
  onConnect: (input: JellyfinConnectInput) => void
}

/**
 * 頁 1：Jellyfin，它的管理員就是 Berth 的擁有者（plan §9.3、M4 票 06、15）。
 *
 * 照 Seerr：先連媒體伺服器。頁首二選一（`ServiceChoice`）——不預選、選了才連；連上之後表單跟著
 * 那一台的狀態走：還沒跑過初始精靈就建立管理員（選既有也一樣），已經有管理員就登入（套件內重裝
 * 保留 config 也一樣）。帳密只交給 Jellyfin，不存下來。擁有者成立之後這一頁的選擇鎖住。
 */
export function OwnerStep({
  status,
  choice,
  claiming,
  refusal,
  claimError,
  onClaim,
  onClaimReset,
  reSignIn,
  note,
  nav,
}: {
  status: SetupStatus
  /** 選擇的兩支 mutation 與畫面上選著、還沒存下的那一格（`SetupPage` 持有）。 */
  choice: ChoiceControls & ChoiceDraft
  claiming: boolean
  /** 後端說不行的那一份（`ownerRefusalOf`）。 */
  refusal: OwnerRefusal | null
  /** 請求沒跑完，而且不是一份認得的拒絕（沒有就是 `null`）。 */
  claimError: unknown
  onClaim: (input: OwnerInput) => void
  /** 收掉上一次送出的結果（拒絕那一句）。`target_changed` 之後重新測試時用（M4 票 28）。 */
  onClaimReset: () => void
  reSignIn: ReSignIn
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 回頭看這一頁時的導覽（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const jellyfin = status.services.find((row) => row.kind === 'jellyfin')
  // 換另一格還在確認：標題與表單不說原本那一台的事（M4 票 09）。
  const switching = choice.draft !== null && choice.draft !== jellyfin?.origin
  const mode = switching ? 'choose' : modeOf(status, connected(jellyfin))
  const reSignInId = useId()

  return (
    <StepFrame cutaway={<OwnerCutaway status={status} mode={mode} />}>
      <h2 className="text-lg font-semibold text-ink">
        {t(`owner.title.${mode}`, { name: status.owner })}
      </h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(`owner.lede.${mode}`, { name: status.owner })}
      </p>
      {note}

      <ServiceChoice
        kind="jellyfin"
        status={status}
        {...choice}
        locked={status.owner ? t('owner.locked') : undefined}
      />

      {mode === 'owned' && jellyfin?.state === 'failed' && jellyfin.reason === 'auth_required' && (
        <section aria-labelledby={`${reSignInId}-title`} className="mt-6">
          <h3 id={`${reSignInId}-title`} className="text-sm font-semibold text-ink">
            {t('owner.reSignIn.title')}
          </h3>
          <p className="mt-1 max-w-prose text-xs text-ink-dim">{t('owner.reSignIn.lede')}</p>
          <JellyfinSignInForm {...reSignIn} signedIn />
        </section>
      )}

      {(mode === 'create' || mode === 'signIn') && jellyfin && (
        <OwnerForm
          // 畫面上的那一台換了（重讀到別人改的位址）就是另一張表單：打好的帳密不留給新的那一台
          // （M4 票 28）。
          key={`${mode} ${jellyfin.base_url} ${jellyfin.server_id}`}
          signsIn={mode === 'signIn'}
          jellyfin={jellyfin}
          claiming={claiming}
          refusal={refusal}
          claimError={claimError}
          onClaim={onClaim}
          retesting={choice.retesting}
          onRetest={() => {
            onClaimReset()
            choice.onRetest(true)
          }}
          sticky={!nav}
        />
      )}
      {nav}
    </StepFrame>
  )
}

/** 這一頁畫哪一種：已成立、還沒選或還沒連上、建立管理員、登入既有的管理員。 */
type OwnerMode = 'owned' | 'choose' | 'signIn' | 'create'

function modeOf(status: SetupStatus, ready: boolean): OwnerMode {
  if (status.owner) return 'owned'
  if (!ready) return 'choose'
  // 登入還是建立由後端說（`owner_signs_in`：那一台已經有管理員），與選套件內或既有無關。
  return status.owner_signs_in ? 'signIn' : 'create'
}

function OwnerForm({
  signsIn,
  jellyfin,
  claiming,
  refusal,
  claimError,
  onClaim,
  retesting,
  onRetest,
  sticky,
}: {
  signsIn: boolean
  /**
   * 畫面上測過的那一台。位址與 ServerId 隨帳密送出，後端比對沒被換過才交給 Jellyfin（M4 票 28）。
   *
   * 來源決定建立時寫進 Jellyfin 初始設定的語言與遠端存取（M4 票 18，使用者拍板）：既有的在畫面上問；
   * 套件內的是 Berth 的，不問——帶 UI 語言、不開遠端存取。登入的那一台已經設過了，不送。
   */
  jellyfin: SetupService
  claiming: boolean
  refusal: OwnerRefusal | null
  claimError: unknown
  onClaim: (input: OwnerInput) => void
  retesting: boolean
  onRetest: () => void
  sticky: boolean
}) {
  const { t, i18n } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [checked, setChecked] = useState(false)
  const [culture, setCulture] = useState(() => localeForUi(i18n.language).ui_culture)
  const [remoteAccess, setRemoteAccess] = useState(false)
  const asksStartup = !signsIn && jellyfin.origin === 'existing'
  const languageId = useId()

  const blank = checked && (!username.trim() || !password)
  // 密碼打兩次只在建立時（Jellyfin 自己的啟動精靈也是）：登入打錯了 Jellyfin 會拒絕，
  // 建立時打錯了沒有人會告訴他。
  const mismatch = checked && !signsIn && password !== confirm

  function submit(event: FormEvent) {
    event.preventDefault()
    setChecked(true)
    if (!username.trim() || !password || (!signsIn && password !== confirm)) return
    const credentials = {
      base_url: jellyfin.base_url,
      server_id: jellyfin.server_id,
      username: username.trim(),
      password,
    }
    if (signsIn) {
      onClaim(credentials)
      return
    }
    const locale = asksStartup
      ? JELLYFIN_LOCALES.find((row) => row.ui_culture === culture)!
      : localeForUi(i18n.language)
    onClaim({ ...credentials, ...locale, remote_access: asksStartup && remoteAccess })
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 grid gap-5">
      <Field
        label={t('owner.field.username')}
        value={username}
        autoComplete="username"
        onChange={(event) => setUsername(event.target.value)}
        error={blank && !username.trim() ? t('owner.error.blank') : undefined}
      />
      <PasswordField
        label={t('owner.field.password')}
        value={password}
        autoComplete={signsIn ? 'current-password' : 'new-password'}
        onChange={(event) => setPassword(event.target.value)}
        error={blank && !password ? t('owner.error.blank') : undefined}
      />
      {!signsIn && (
        <PasswordField
          label={t('owner.field.confirm')}
          value={confirm}
          autoComplete="new-password"
          onChange={(event) => setConfirm(event.target.value)}
          error={mismatch ? t('owner.error.mismatch') : undefined}
        />
      )}
      {asksStartup && (
        <>
          <p className="grid gap-2">
            <label htmlFor={languageId} className="label text-ink-dim">
              {t('owner.startup.language')}
            </label>
            <select
              id={languageId}
              value={culture}
              aria-describedby={`${languageId}-hint`}
              onChange={(event) => setCulture(event.target.value)}
              className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
            >
              {JELLYFIN_LOCALES.map((row) => (
                <option key={row.ui_culture} value={row.ui_culture}>
                  {localeLabel(row, i18n.language)}
                </option>
              ))}
            </select>
            <span id={`${languageId}-hint`} className="text-xs text-ink-dim">
              {t('owner.startup.languageHint')}
            </span>
          </p>
          <Checkbox
            label={t('owner.startup.remote')}
            hint={t('owner.startup.remoteHint')}
            checked={remoteAccess}
            onChange={setRemoteAccess}
          />
        </>
      )}
      {/* 拒絕的那一句在送出鈕上方：窄版的送出鈕吸在底部，放在它下面要捲才看得到（critique）。 */}
      {refusal ? (
        <div>
          <Notice signal="blocked" label={t('common.failed')}>
            {t(`owner.refused.${refusal.reason}`)}
          </Notice>
          {refusal.reason === 'target_changed' && (
            <p className="mt-3">
              <GhostButton type="button" busy={retesting} onClick={onRetest}>
                {retesting ? t('connection.retesting') : t('connection.retest')}
              </GhostButton>
            </p>
          )}
          {/* Jellyfin 那一步的原文（例如版本太舊的英文句子）收進技術細節（M4 票 21）。 */}
          <TechnicalDetails lines={[refusal.detail]} />
        </div>
      ) : (
        // 這張表單只在還沒有擁有者時送出：門禁要求登入就是別處搶先成立了（M4 票 25，實測 E12-11）。
        claimError !== null &&
        claimError !== undefined && <RequestFailed error={claimError} ownerPending />
      )}
      <div className={sticky ? STICKY_ACTION : ''}>
        <PrimaryButton type="submit" busy={claiming}>
          {claiming
            ? t(signsIn ? 'owner.submitting.signIn' : 'owner.submitting.create')
            : t(signsIn ? 'owner.submit.signIn' : 'owner.submit.create')}
        </PrimaryButton>
      </div>
    </form>
  )
}

/** 剖面：將會做什麼。選之前兩種都說；連上之後照那一台的狀態說。 */
function OwnerCutaway({ status, mode }: { status: SetupStatus; mode: OwnerMode }) {
  const { t } = useTranslation()
  const jellyfin = status.services.find((row) => row.kind === 'jellyfin')

  return (
    <Cutaway title={t('owner.cutaway.title')}>
      {jellyfin && (
        <CutawayRow
          code
          term={jellyfin.base_url}
          value={[jellyfin.detail, t(ORIGIN_LABEL[jellyfin.origin])].filter(Boolean).join(' · ')}
        />
      )}
      {mode === 'create' && (
        <>
          <CutawayRow term={t('owner.cutaway.create')} value={t('owner.cutaway.admin')} />
          <CutawayRow term={t('owner.cutaway.finish')} value={t('owner.cutaway.startup')} />
        </>
      )}
      {/* 還沒選或還沒連上：建立還是登入要看那一台有沒有管理員，這時說成「建立」是替它先決定了
          （M4 票 21：選既有、還沒測時這裡列的是套件內的動作）。 */}
      {mode === 'choose' && (
        <CutawayRow term={t('owner.cutaway.form')} value={t('owner.cutaway.depends')} />
      )}
      {mode === 'signIn' && (
        <CutawayRow term={t('owner.cutaway.change')} value={t('owner.cutaway.nothing')} />
      )}
      {mode === 'owned' ? (
        <CutawayRow term={t('owner.cutaway.owner')} value={status.owner} />
      ) : (
        <CutawayRow term={t('owner.cutaway.create')} value={t('owner.cutaway.apiKey')} />
      )}
      <CutawayRow term={t('owner.cutaway.stored')} value={t('owner.cutaway.password')} muted />
    </Cutaway>
  )
}

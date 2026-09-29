import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { OwnerInput, OwnerRefusal, SetupStatus } from '../api/setup'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { ORIGIN_LABEL } from '../components/services'
import { STICKY_ACTION, Field, Notice, PasswordField, PrimaryButton } from '../components/controls'
import { ServiceChoice, type ChoiceControls } from './ServiceChoice'
import { connected } from './signals'
import { StepFrame } from './StepFrame'

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
  claimFailed,
  onClaim,
  note,
  nav,
}: {
  status: SetupStatus
  choice: ChoiceControls
  claiming: boolean
  /** 後端說不行的那一份（`ownerRefusalOf`）。 */
  refusal: OwnerRefusal | null
  /** 請求沒跑完，而且不是一份認得的拒絕。 */
  claimFailed: boolean
  onClaim: (input: OwnerInput) => void
  /** 回頭看的說明（`RevisitNote`），這一頁做完了才有。 */
  note?: ReactNode
  /** 回頭看這一頁時的導覽（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const jellyfin = status.services.find((row) => row.kind === 'jellyfin')
  const mode = modeOf(status, connected(jellyfin))

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

      {(mode === 'create' || mode === 'signIn') && (
        <OwnerForm
          key={mode}
          signsIn={mode === 'signIn'}
          claiming={claiming}
          refusal={refusal}
          claimFailed={claimFailed}
          onClaim={onClaim}
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
  claiming,
  refusal,
  claimFailed,
  onClaim,
  sticky,
}: {
  signsIn: boolean
  claiming: boolean
  refusal: OwnerRefusal | null
  claimFailed: boolean
  onClaim: (input: OwnerInput) => void
  sticky: boolean
}) {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [checked, setChecked] = useState(false)

  const blank = checked && (!username.trim() || !password)
  // 密碼打兩次只在建立時（Jellyfin 自己的啟動精靈也是）：登入打錯了 Jellyfin 會拒絕，
  // 建立時打錯了沒有人會告訴他。
  const mismatch = checked && !signsIn && password !== confirm

  function submit(event: FormEvent) {
    event.preventDefault()
    setChecked(true)
    if (!username.trim() || !password || (!signsIn && password !== confirm)) return
    onClaim({ username: username.trim(), password })
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
      {/* 拒絕的那一句在送出鈕上方：窄版的送出鈕吸在底部，放在它下面要捲才看得到（critique）。 */}
      {refusal ? (
        <Notice signal="blocked" label={t('common.failed')}>
          {t(`owner.refused.${refusal.reason}`)}
          {refusal.detail && <span className="value mt-1 block text-xs">{refusal.detail}</span>}
        </Notice>
      ) : (
        claimFailed && (
          <Notice signal="blocked" label={t('common.failed')}>
            {t('owner.error.failed')}
          </Notice>
        )
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
      {(mode === 'create' || mode === 'choose') && (
        <>
          <CutawayRow term={t('owner.cutaway.create')} value={t('owner.cutaway.admin')} />
          <CutawayRow term={t('owner.cutaway.finish')} value={t('owner.cutaway.startup')} />
        </>
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

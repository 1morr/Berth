import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ConnectInput, OwnerInput, OwnerRefusal, SetupStatus } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { ORIGIN_LABEL } from '../components/services'
import {
  STICKY_ACTION,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { MooringLine } from './MooringLine'
import { probeEndpoint } from './signals'
import { StepFrame } from './StepFrame'

/**
 * 第 1 步：擁有者（plan §9.3 第 1 步、M4 票 06，`.scratch/m4/wizard-owner-shape.md`）。
 *
 * 照 Seerr：先找到 Jellyfin，它的管理員就是 Berth 的擁有者。Berth 沒有自己的帳號——套件內的
 * 那一台由 Berth 代建管理員，既有的那一台用它自己的管理員登入；帳密只交給 Jellyfin，不存下來。
 *
 * 工作面先是 Jellyfin 那一條纜繩（找不到時就地展開位址表單），找到了才給帳密表單。
 */
export function OwnerStep({
  status,
  probing,
  detectFailed,
  connecting,
  redetecting,
  claiming,
  refusal,
  claimFailed,
  onDetect,
  onConnect,
  onRedetect,
  onClaim,
  nav,
}: {
  status: SetupStatus
  /** 正在找 Jellyfin（第一次、重試或輪詢）。 */
  probing: boolean
  /** 探測本身沒跑完（後端沒回判定）。 */
  detectFailed: boolean
  connecting: boolean
  redetecting: boolean
  claiming: boolean
  /** 後端說不行的那一份（`ownerRefusalOf`）。 */
  refusal: OwnerRefusal | null
  /** 請求沒跑完，而且不是一份認得的拒絕。 */
  claimFailed: boolean
  onDetect: (restart: boolean) => void
  onConnect: (kind: ServiceKind, input: ConnectInput) => void
  onRedetect: (kind: ServiceKind) => void
  onClaim: (input: OwnerInput) => void
  /** 回頭看第 1 步時的導覽（`BerthNav`）。 */
  nav?: ReactNode
}) {
  const { t } = useTranslation()
  const jellyfin = status.services.find((row) => row.kind === 'jellyfin')
  const found = jellyfin !== undefined && jellyfin.resolved && !probing
  const mode = modeOf(status, found)
  // 找到之後位址表單收起來，只留一顆「換一台」（critique：兩份表單搶同一個工作面）。
  // 探到的是套件內那一台時沒有表單可開，這顆鍵也就不給。
  const [changing, setChanging] = useState(false)
  const changeable = found && jellyfin.origin === 'existing'

  return (
    <StepFrame cutaway={<OwnerCutaway status={status} mode={mode} />}>
      <h2 className="text-lg font-semibold text-ink">
        {t(`owner.title.${mode}`, { name: status.owner })}
      </h2>
      <p className="mt-2 max-w-prose text-sm text-ink-dim">
        {t(`owner.lede.${mode}`, { name: status.owner })}
      </p>

      {mode === 'owned' ? null : (
        <>
          <div aria-live="polite" aria-busy={probing}>
            <ol className="mt-6 grid gap-3">
              <MooringLine
                kind="jellyfin"
                endpoint={probeEndpoint(status, 'jellyfin')}
                detection={jellyfin}
                tying={probing}
                waitedSeconds={status.waited_seconds}
                windowSeconds={status.window_seconds}
                connecting={connecting}
                redetecting={redetecting}
                onConnect={onConnect}
                onRedetect={onRedetect}
                collapsed={found && !changing}
              />
            </ol>
          </div>
          {changeable && !changing && (
            <div className="mt-3">
              <GhostButton type="button" onClick={() => setChanging(true)}>
                {t('owner.change')}
              </GhostButton>
            </div>
          )}
          {detectFailed && (
            <div className="mt-4">
              <Notice signal="blocked" label={t('common.failed')}>
                {t('detect.failed')}
              </Notice>
            </div>
          )}
          {mode === 'finding' ? (
            !probing &&
            jellyfin?.origin !== 'pending' && (
              <div className={`mt-6 ${STICKY_ACTION}`}>
                <GhostButton type="button" onClick={() => onDetect(jellyfin?.origin === 'timeout')}>
                  {jellyfin?.origin === 'timeout' ? t('detect.retry') : t('detect.rerun')}
                </GhostButton>
              </div>
            )
          ) : (
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
        </>
      )}
      {nav}
    </StepFrame>
  )
}

/** 這一步畫哪一種：已成立、還在找 Jellyfin、登入既有的、建立套件內的管理員。 */
type OwnerMode = 'owned' | 'finding' | 'signIn' | 'create'

function modeOf(status: SetupStatus, found: boolean): OwnerMode {
  if (status.owner) return 'owned'
  if (!found) return 'finding'
  // 登入還是建立由後端說（`owner_signs_in`：既有，或套件內那一台的管理員已經建好）。
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

/** 剖面：將會做什麼。照判定說話，找到 Jellyfin 之前只說會去哪裡找。 */
function OwnerCutaway({ status, mode }: { status: SetupStatus; mode: OwnerMode }) {
  const { t } = useTranslation()
  const jellyfin = status.services.find((row) => row.kind === 'jellyfin')
  const endpoint = jellyfin?.base_url || status.probe_targets.jellyfin

  return (
    <Cutaway title={t('owner.cutaway.title')}>
      <CutawayRow code term={endpoint} value={t('service.jellyfin')} />
      {jellyfin && (jellyfin.origin === 'bundled' || jellyfin.origin === 'existing') && (
        <CutawayRow
          term={t('owner.cutaway.found')}
          value={[jellyfin.detail, t(ORIGIN_LABEL[jellyfin.origin])].filter(Boolean).join(' · ')}
        />
      )}
      {mode === 'finding' && (
        <CutawayRow term={t('detect.cutaway.verdict')} value={t('detect.cutaway.jellyfin')} />
      )}
      {mode === 'create' && (
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

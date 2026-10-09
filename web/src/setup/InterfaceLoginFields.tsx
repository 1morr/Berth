import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { Checkbox, Field, GhostButton, Notice, PasswordField } from '../components/controls'
import {
  LOGIN_RULES,
  type InterfaceLoginForm,
  type LoginProblems,
  type LoginService,
} from './interfaceLogin'

/** 產品名不翻譯：人話裡的 `{{service}}`。 */
const PRODUCT = { qbittorrent: 'qBittorrent', prowlarr: 'Prowlarr' } as const satisfies Record<
  LoginService,
  string
>

/**
 * 精靈的介面登入欄位（M4 票 07、15）：頁 2、頁 4 共用。設定頁沒有沿用，只用下面的 `NewLoginFields`（M4 票 78）。
 *
 * 上面一個「沿用 Jellyfin 帳密」預設勾選：帳號是擁有者、密碼打一次（Jellyfin 會驗它）。取消勾選是
 * 自設的三格：帳號、密碼、再一次密碼。說明句先講這是**那個服務自己的登入**：Berth 用不到它。
 */
export function InterfaceLoginFields({
  service,
  form,
}: {
  service: LoginService
  form: InterfaceLoginForm
}) {
  const { t } = useTranslation()
  const { draft, problems, owner, rules } = form
  const rule = {
    service: PRODUCT[service],
    owner,
    usernameMin: rules?.usernameMin ?? 0,
    passwordMin: rules?.passwordMin ?? 0,
  }
  // 沿用時帳號那一格不在畫面上：擁有者的名字不合規則也說在密碼那一格，而且先說它——改密碼救不了。
  const reuseError = problems.username
    ? t('interfaceLogin.error.reuseUsername', { ...rule, min: rule.usernameMin })
    : problems.password === 'short'
      ? t('interfaceLogin.error.reusePasswordShort', { ...rule, min: rule.passwordMin })
      : problems.password
        ? t('interfaceLogin.error.blank')
        : undefined

  return (
    <fieldset className="grid gap-5 border-2 border-rule bg-well px-4 py-4">
      <legend className="label px-2 text-ink-dim">{t(`interfaceLogin.${service}.legend`)}</legend>
      <p className="max-w-prose text-xs text-ink-dim">{t(`interfaceLogin.${service}.lede`)}</p>
      {owner && (
        <Checkbox
          label={t('interfaceLogin.reuse', { owner })}
          hint={form.reuse ? t('interfaceLogin.reuseHint', { owner }) : undefined}
          checked={form.reuse}
          onChange={form.setReuse}
        />
      )}
      {form.reuse ? (
        <PasswordField
          label={t('interfaceLogin.ownerPassword', { owner })}
          value={draft.password}
          autoComplete="current-password"
          onChange={(event) => form.change({ password: event.target.value })}
          error={reuseError}
        />
      ) : (
        <NewLoginFields service={service} form={form} />
      )}
    </fieldset>
  )
}

/**
 * 自設一組登入的三格：帳號、密碼、再一次密碼（M4 票 07）。精靈取消「沿用」時與設定頁（M4 票 78，那裡
 * 沒有沿用、密碼那一格叫「新密碼」）共用，驗證說法同一套。
 */
export function NewLoginFields({
  service,
  form,
  passwordLabel,
}: {
  service: LoginService
  form: InterfaceLoginForm
  /** 密碼那一格的名字；預設「密碼」。 */
  passwordLabel?: string
}) {
  const { t } = useTranslation()
  const { draft, problems, rules } = form
  const rule = {
    service: PRODUCT[service],
    usernameMin: rules?.usernameMin ?? 0,
    passwordMin: rules?.passwordMin ?? 0,
  }

  return (
    <>
      <Field
        label={t('interfaceLogin.username')}
        value={draft.username}
        autoComplete="off"
        onChange={(event) => form.change({ username: event.target.value })}
        error={usernameError(t, problems.username, rule)}
      />
      <PasswordField
        label={passwordLabel ?? t('interfaceLogin.password')}
        value={draft.password}
        autoComplete="new-password"
        onChange={(event) => form.change({ password: event.target.value })}
        error={
          problems.password === 'short'
            ? t('interfaceLogin.error.passwordShort', { ...rule, min: rule.passwordMin })
            : problems.password
              ? t('interfaceLogin.error.blank')
              : undefined
        }
      />
      <PasswordField
        label={t('interfaceLogin.confirm')}
        value={draft.confirm}
        autoComplete="new-password"
        onChange={(event) => form.change({ confirm: event.target.value })}
        error={problems.confirm ? t('interfaceLogin.error.mismatch') : undefined}
      />
    </>
  )
}

function usernameError(
  t: TFunction,
  problem: LoginProblems['username'],
  rule: { service: string; usernameMin: number },
): string | undefined {
  switch (problem) {
    case 'blank':
      return t('interfaceLogin.error.blank')
    case 'short':
      return t('interfaceLogin.error.usernameShort', { ...rule, min: rule.usernameMin })
    case 'colon':
      return t('interfaceLogin.error.usernameColon', rule)
    case undefined:
      return undefined
  }
}

/**
 * 泊位上的那一塊：還沒設過就是三格（必填）；設過了說出帳號，按「更換」才打開，不按就是照舊。
 */
export function BerthLogin({
  service,
  current,
  form,
}: {
  service: LoginService
  /** 那一台的帳號（Berth 設下的，或它自己就設過的），空字串是還沒設過。 */
  current: string
  form: InterfaceLoginForm
}) {
  const { t } = useTranslation()

  if (form.open) return <InterfaceLoginFields service={service} form={form} />
  return (
    <div className="flex flex-wrap items-center gap-3 border-2 border-rule bg-well px-4 py-3">
      <p className="text-sm text-ink">
        {t(`interfaceLogin.${service}.set`)} <span className="value font-semibold">{current}</span>
      </p>
      <GhostButton type="button" onClick={form.openFields}>
        {t('interfaceLogin.change')}
      </GhostButton>
    </div>
  )
}

/**
 * 頁 1 帶過來的那一組正在自動送（M4 票 40）：取代欄位與按鈕，說的是沿用誰的帳密。
 */
export function CarriedApplying({ owner }: { owner: string }) {
  const { t } = useTranslation()

  return (
    <div aria-live="polite">
      <Notice signal="working" label={t('status.running')}>
        {t('interfaceLogin.carried.applying', { owner })}
      </Notice>
    </div>
  )
}

/**
 * 頁 1 帶過來的那一組不合 qBittorrent 的規則（M4 票 40、票 26）：說為什麼不能沿用，欄位一開始就是自設的
 * 三格。只有 qBittorrent 有規則（`LOGIN_RULES`），Prowlarr 永遠沿用得了。
 */
export function CarriedUnfit({ owner, problems }: { owner: string; problems: LoginProblems }) {
  const { t } = useTranslation()
  const rules = LOGIN_RULES.qbittorrent
  const rule = { service: PRODUCT.qbittorrent, owner }

  return (
    <Notice signal="assigned" label={t('interfaceLogin.carried.unfitLabel')}>
      {problems.username
        ? t('interfaceLogin.carried.unfitUsername', { ...rule, min: rules.usernameMin })
        : t('interfaceLogin.carried.unfitPassword', { ...rule, min: rules.passwordMin })}
    </Notice>
  )
}

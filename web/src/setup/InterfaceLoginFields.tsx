import { useTranslation } from 'react-i18next'

import { Field, GhostButton, PasswordField } from '../components/controls'
import type { InterfaceLoginForm } from './interfaceLogin'

/** 哪一個服務的介面：文案說得出是誰的登入、打開哪個網址。 */
export type LoginService = 'qbittorrent' | 'prowlarr'

/**
 * 介面登入的三格（M4 票 07）：帳號、密碼、再一次密碼。精靈兩個泊位與設定頁共用。
 *
 * 說明句先講這是**那個服務自己的登入**：Berth 用不到它，是給使用者自己打開介面用的。
 */
export function InterfaceLoginFields({
  service,
  form,
}: {
  service: LoginService
  form: InterfaceLoginForm
}) {
  const { t } = useTranslation()
  const { draft, problems } = form

  return (
    <fieldset className="grid gap-5 border-2 border-rule bg-well px-4 py-4">
      <legend className="label px-2 text-ink-dim">{t(`interfaceLogin.${service}.legend`)}</legend>
      <p className="max-w-prose text-xs text-ink-dim">{t(`interfaceLogin.${service}.lede`)}</p>
      <Field
        label={t('interfaceLogin.username')}
        value={draft.username}
        autoComplete="off"
        onChange={(event) => form.change({ username: event.target.value })}
        error={problems.username ? t('interfaceLogin.error.blank') : undefined}
      />
      <PasswordField
        label={t('interfaceLogin.password')}
        value={draft.password}
        autoComplete="new-password"
        onChange={(event) => form.change({ password: event.target.value })}
        error={problems.password ? t('interfaceLogin.error.blank') : undefined}
      />
      <PasswordField
        label={t('interfaceLogin.confirm')}
        value={draft.confirm}
        autoComplete="new-password"
        onChange={(event) => form.change({ confirm: event.target.value })}
        error={problems.confirm ? t('interfaceLogin.error.mismatch') : undefined}
      />
    </fieldset>
  )
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
  /** Berth 設下的帳號，空字串是還沒設過。 */
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

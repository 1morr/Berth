import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  notifyQueryOptions,
  notifyRefusalOf,
  saveBotToken,
  saveDiscordId,
  sendTestMessage,
  type DeliveryFailure,
  type Notify,
  type NotifyRefusal,
  type NotifyTest,
} from '../api/notify'
import {
  ConfirmAction,
  Field,
  GHOST_LINK,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
  TEXT_LINK,
} from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'
import type { Language } from '../i18n/resources'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'

/** Discord Developer Portal：建 application 與 bot 的地方。這一頁不教學，給一個連結。 */
const DEVELOPER_PORTAL = 'https://discord.com/developers/applications'

type Key = ParseKeys

/** 每一種測試失敗的人話與補法。少一種是編譯錯誤；`rate_limited` 的補法有秒數時另外挑（`failureFix`）。 */
const FAILURE_TEXT = {
  unauthorized: {
    what: 'settings.notifyPage.test.failure.unauthorized.what',
    fix: 'settings.notifyPage.test.failure.unauthorized.fix',
  },
  recipient_unreachable: {
    what: 'settings.notifyPage.test.failure.recipient_unreachable.what',
    fix: 'settings.notifyPage.test.failure.recipient_unreachable.fix',
  },
  rate_limited: {
    what: 'settings.notifyPage.test.failure.rate_limited.what',
    fix: 'settings.notifyPage.test.failure.rate_limited.fixUnknown',
  },
  rejected: {
    what: 'settings.notifyPage.test.failure.rejected.what',
    fix: 'settings.notifyPage.test.failure.rejected.fix',
  },
  unavailable: {
    what: 'settings.notifyPage.test.failure.unavailable.what',
    fix: 'settings.notifyPage.test.failure.unavailable.fix',
  },
} as const satisfies Record<DeliveryFailure, { what: Key; fix: Key }>

/** 每一種拒絕理由的一句話。少一種是編譯錯誤。 */
const REFUSAL_TEXT = {
  token_rejected: 'settings.notifyPage.refusal.token_rejected',
  discord_unreachable: 'settings.notifyPage.refusal.discord_unreachable',
  discord_id_invalid: 'settings.notifyPage.refusal.discord_id_invalid',
  bot_missing: 'settings.notifyPage.refusal.bot_missing',
  discord_id_missing: 'settings.notifyPage.refusal.discord_id_missing',
} as const satisfies Record<NotifyRefusal, Key>

/** 這一頁是用哪個語言在看（通知就用它寫）。 */
function useUiLanguage(): Language {
  const { i18n } = useTranslation()
  return i18n.language === 'zh-Hant' ? 'zh-Hant' : 'en'
}

/**
 * 設定 → 通知（M4 票 123，`.scratch/m4/notify-settings-shape.md`）。它不是泊位：沒有泊位號、不在泊位板上。
 * 三段：Discord bot（管理員一次性的設定）、我的 Discord、測試。
 */
export function NotifySettingsPage() {
  const { t } = useTranslation()
  const notify = useQuery(notifyQueryOptions)

  return (
    <SettingsFrame title={t('settings.notifyPage.title')} lede={t('settings.notifyPage.lede')}>
      {notify.data ? (
        <>
          <BotSection notify={notify.data} />
          <MySection notify={notify.data} />
          <TestSection notify={notify.data} />
        </>
      ) : notify.isError ? (
        <RequestFailed error={notify.error} lead={t('settings.notifyPage.readFailed')} />
      ) : (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      )}
    </SettingsFrame>
  )
}

/** 存下之後把回來的狀態放進快取：三段讀同一份。 */
function useNotifyCache() {
  const queryClient = useQueryClient()
  return (next: Notify) => queryClient.setQueryData(notifyQueryOptions.queryKey, next)
}

/** 一次命令沒成的那一格：Discord 說不行的用人話加原文，其餘照請求為什麼沒成說。 */
function Failed({ error, lead }: { error: unknown; lead: string }) {
  const { t } = useTranslation()
  const refusal = notifyRefusalOf(error)
  if (refusal === null) return <RequestFailed error={error} lead={lead} />
  return (
    <div className="grid gap-1">
      <Notice signal="blocked" label={t('common.failed')}>
        {t(REFUSAL_TEXT[refusal.reason])}
      </Notice>
      <TechnicalDetails lines={[refusal.detail]} />
    </div>
  )
}

function BotSection({ notify }: { notify: Notify }) {
  const { t } = useTranslation()
  const cache = useNotifyCache()
  const [token, setToken] = useState('')
  const [blank, setBlank] = useState(false)
  const save = useMutation({
    mutationFn: saveBotToken,
    onSuccess: (next) => {
      cache(next)
      setToken('')
      // 狀態句說的是最後一個動作：先存再移除時不能還說「已儲存」。
      remove.reset()
    },
  })
  const remove = useMutation({
    mutationFn: () => saveBotToken(''),
    onSuccess: (next) => {
      cache(next)
      save.reset()
    },
  })
  const rejected = notifyRefusalOf(save.error)?.reason === 'token_rejected'
  const statusId = useId()

  return (
    <SettingsSection
      id="notify-bot"
      title={t('settings.notifyPage.bot.title')}
      lede={t('settings.notifyPage.bot.lede')}
    >
      <div className="grid gap-4">
        <a
          href={DEVELOPER_PORTAL}
          target="_blank"
          rel="noreferrer noopener"
          className={`${TEXT_LINK} justify-self-start`}
        >
          {t('settings.notifyPage.bot.portal')}
        </a>

        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[max-content_minmax(0,1fr)]">
          <dt className="label text-ink-dim">{t('settings.notifyPage.bot.status')}</dt>
          <dd className="flex flex-wrap items-center gap-2 text-sm text-ink">
            {notify.bot_configured ? (
              <>
                <span className="label bg-deck px-2 py-1.5 text-ink">
                  {t('settings.notifyPage.bot.configured')}
                </span>
                <span className="value wrap-anywhere">{notify.bot_name}</span>
              </>
            ) : (
              <span className="text-ink-dim">{t('settings.notifyPage.bot.unconfigured')}</span>
            )}
          </dd>
        </dl>

        {/* 空著按儲存不送：空字串在後端是「清掉」，那件事只走下面的「移除 token」。 */}
        <form
          noValidate
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (!token.trim()) {
              setBlank(true)
              return
            }
            save.mutate(token.trim())
          }}
        >
          <PasswordField
            label={t('settings.notifyPage.bot.tokenLabel')}
            value={token}
            autoComplete="off"
            placeholder={t(
              notify.bot_configured
                ? 'settings.notifyPage.bot.placeholderSet'
                : 'settings.notifyPage.bot.placeholder',
            )}
            hint={t('settings.notifyPage.bot.hint')}
            error={
              blank
                ? t('settings.notifyPage.bot.blank')
                : rejected
                  ? t(REFUSAL_TEXT.token_rejected)
                  : undefined
            }
            onChange={(event) => {
              setToken(event.target.value)
              setBlank(false)
              save.reset()
            }}
          />
          <div className="justify-self-start">
            <GhostButton type="submit" busy={save.isPending}>
              {t(
                save.isPending ? 'settings.notifyPage.bot.saving' : 'settings.notifyPage.bot.save',
              )}
            </GhostButton>
          </div>
        </form>

        {save.isError && !rejected && (
          <Failed error={save.error} lead={t('settings.notifyPage.bot.failed')} />
        )}
        <p id={statusId} aria-live="polite" className="text-xs text-ink-dim">
          {save.isSuccess
            ? t('settings.notifyPage.bot.saved')
            : remove.isSuccess
              ? t('settings.notifyPage.bot.removed')
              : ''}
        </p>

        {notify.bot_configured && notify.invite_url && <Invite url={notify.invite_url} />}

        {notify.bot_configured && (
          <div className="grid justify-items-start gap-2">
            <ConfirmAction
              label={t('settings.notifyPage.bot.remove')}
              confirmLabel={t('settings.notifyPage.bot.removeConfirm')}
              pendingLabel={t('settings.notifyPage.bot.removing')}
              pending={remove.isPending}
              warning={t('settings.notifyPage.bot.removeWarning')}
              onConfirm={() => remove.mutate()}
            />
            {remove.isError && (
              <Failed error={remove.error} lead={t('settings.notifyPage.bot.failed')} />
            )}
          </div>
        )}
      </div>
    </SettingsSection>
  )
}

/** 邀請連結：完整網址（機器字串，會換行）、複製、在新分頁開啟，與 bot 要和你同一個伺服器的那一句。 */
function Invite({ url }: { url: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // 沒有剪貼簿權限就算了，網址本身選得起來。
      setCopied(false)
    }
  }

  return (
    <div className="grid gap-2">
      <p className="label text-ink-dim">{t('settings.notifyPage.bot.invite')}</p>
      <p className="value text-xs wrap-anywhere text-ink">{url}</p>
      <div className="flex flex-wrap gap-2">
        <GhostButton type="button" onClick={() => void copy()}>
          {t(copied ? 'common.copied' : 'common.copy')}
        </GhostButton>
        <a
          href={url}
          target="_blank"
          rel="noreferrer noopener"
          className={`${GHOST_LINK} text-center`}
        >
          {t('settings.notifyPage.bot.inviteOpen')}
        </a>
      </div>
      <p className="max-w-prose text-xs text-ink-dim">{t('settings.notifyPage.bot.inviteHint')}</p>
    </div>
  )
}

function MySection({ notify }: { notify: Notify }) {
  const { t } = useTranslation()
  const cache = useNotifyCache()
  const language = useUiLanguage()
  const [id, setId] = useState(notify.discord_user_id)
  const save = useMutation({
    mutationFn: () => saveDiscordId(id.trim(), language),
    onSuccess: cache,
  })
  const invalid = notifyRefusalOf(save.error)?.reason === 'discord_id_invalid'
  const name = (code: Language) => t(`settings.notifyPage.languageName.${code}`)

  return (
    <SettingsSection id="notify-me" title={t('settings.notifyPage.me.title')}>
      <form
        noValidate
        className="grid gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <Field
          label={t('settings.notifyPage.me.idLabel')}
          value={id}
          inputMode="numeric"
          autoComplete="off"
          placeholder={t('settings.notifyPage.me.idPlaceholder')}
          hint={t('settings.notifyPage.me.howTo')}
          error={invalid ? t(REFUSAL_TEXT.discord_id_invalid) : undefined}
          onChange={(event) => {
            setId(event.target.value)
            save.reset()
          }}
        />
        <p className="max-w-prose text-xs text-ink-dim">
          {t('settings.notifyPage.me.language', { language: name(language) })}
          {notify.discord_user_id && notify.language !== language && (
            <> {t('settings.notifyPage.me.savedLanguage', { language: name(notify.language) })}</>
          )}
        </p>
        <div className="justify-self-start">
          <GhostButton type="submit" busy={save.isPending}>
            {t(save.isPending ? 'settings.notifyPage.me.saving' : 'settings.notifyPage.me.save')}
          </GhostButton>
        </div>
        {save.isError && !invalid && (
          <Failed error={save.error} lead={t('settings.notifyPage.me.failed')} />
        )}
        <p aria-live="polite" className="text-xs text-ink-dim">
          {save.isSuccess ? t('settings.notifyPage.me.saved') : ''}
        </p>
      </form>
    </SettingsSection>
  )
}

function TestSection({ notify }: { notify: Notify }) {
  const { t } = useTranslation()
  const missingId = notify.discord_user_id === ''
  const missingBot = !notify.bot_configured
  const missing = missingBot
    ? missingId
      ? 'settings.notifyPage.test.missingBoth'
      : 'settings.notifyPage.test.missingBot'
    : missingId
      ? 'settings.notifyPage.test.missingId'
      : null
  const test = useMutation({ mutationFn: sendTestMessage })
  const missingText = useId()

  return (
    <SettingsSection id="notify-test" title={t('settings.notifyPage.test.title')}>
      <div className="grid gap-3">
        {/* 缺東西時鍵照樣在 Tab 順序上、念得出「不可用」與缺什麼，不是 `disabled`（`busy` 的理由）。 */}
        <PrimaryButton
          type="button"
          busy={test.isPending || missing !== null}
          aria-describedby={missing ? missingText : undefined}
          onClick={() => test.mutate()}
        >
          {t(test.isPending ? 'settings.notifyPage.test.sending' : 'settings.notifyPage.test.send')}
        </PrimaryButton>
        {missing && (
          <p id={missingText} className="text-xs text-ink-dim">
            {t(missing)}
          </p>
        )}
        {/* live region 常駐、結果放進去：跟結果同一次掛上的話不會被念出來。 */}
        <div aria-live="polite" aria-busy={test.isPending} className="grid gap-1">
          {test.data && <TestResult result={test.data} />}
          {test.isError && (
            <Failed error={test.error} lead={t('settings.notifyPage.test.failed')} />
          )}
        </div>
      </div>
    </SettingsSection>
  )
}

function TestResult({ result }: { result: NotifyTest }): ReactNode {
  const { t } = useTranslation()
  if (result.delivered || result.failure === null) {
    return (
      <Notice signal="secured" label={t('settings.notifyPage.test.delivered')}>
        {t('settings.notifyPage.test.deliveredBody')}
      </Notice>
    )
  }
  const text = FAILURE_TEXT[result.failure]
  // 限速有秒數就說秒數；沒有就說「等幾秒」。
  const wait = result.failure === 'rate_limited' ? result.retry_after : null
  return (
    <>
      <Notice signal="blocked" label={t('common.failed')}>
        <span className="grid gap-1">
          <span>{t(text.what)}</span>
          <span>
            {wait === null
              ? t(text.fix)
              : t('settings.notifyPage.test.failure.rate_limited.fix', { count: Math.ceil(wait) })}
          </span>
        </span>
      </Notice>
      <TechnicalDetails lines={[result.failure, result.detail]} />
    </>
  )
}

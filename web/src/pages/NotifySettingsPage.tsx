import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import {
  botQueryOptions,
  myNotifyQueryOptions,
  notifyRefusalOf,
  saveBerthUrl,
  saveBotToken,
  saveMine,
  sendTestMessage,
  type DeliveryFailure,
  type MyNotify,
  type NotificationKind,
  type NotifyBot,
  type NotifyRefusal,
  type NotifyTest,
} from '../api/notify'
import {
  Checkbox,
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
import { Timestamp } from '../components/Timestamp'
import type { Language } from '../i18n/resources'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'

/** Discord Developer Portal：建 application 與 bot 的地方。這一頁不教學，給一個連結。 */
const DEVELOPER_PORTAL = 'https://discord.com/developers/applications'

type Key = ParseKeys

/**
 * 每一種測試失敗的人話與補法。少一種是編譯錯誤；`rate_limited` 的補法有秒數時另外挑（`TestResult`）。
 * `userFix` 是一般使用者看的補法：token 與邀請連結在管理員那一半，他自己補不了，要說找管理員。
 */
const FAILURE_TEXT = {
  unauthorized: {
    what: 'settings.notifyPage.test.failure.unauthorized.what',
    fix: 'settings.notifyPage.test.failure.unauthorized.fix',
    userFix: 'settings.notifyPage.test.failure.unauthorized.userFix',
  },
  recipient_unreachable: {
    what: 'settings.notifyPage.test.failure.recipient_unreachable.what',
    fix: 'settings.notifyPage.test.failure.recipient_unreachable.fix',
    userFix: 'settings.notifyPage.test.failure.recipient_unreachable.userFix',
  },
  rate_limited: {
    what: 'settings.notifyPage.test.failure.rate_limited.what',
    fix: 'settings.notifyPage.test.failure.rate_limited.fixUnknown',
    userFix: 'settings.notifyPage.test.failure.rate_limited.fixUnknown',
  },
  rejected: {
    what: 'settings.notifyPage.test.failure.rejected.what',
    fix: 'settings.notifyPage.test.failure.rejected.fix',
    userFix: 'settings.notifyPage.test.failure.rejected.fix',
  },
  unavailable: {
    what: 'settings.notifyPage.test.failure.unavailable.what',
    fix: 'settings.notifyPage.test.failure.unavailable.fix',
    userFix: 'settings.notifyPage.test.failure.unavailable.fix',
  },
} as const satisfies Record<DeliveryFailure, { what: Key; fix: Key; userFix: Key }>

/** 勾選的每一種：標籤與一句說明。少一種是編譯錯誤（後端加了種類，這裡就要說它是什麼）。 */
const KIND_TEXT = {
  ready: {
    label: 'settings.notifyPage.me.kind.ready.label',
    hint: 'settings.notifyPage.me.kind.ready.hint',
  },
  downloading: {
    label: 'settings.notifyPage.me.kind.downloading.label',
    hint: 'settings.notifyPage.me.kind.downloading.hint',
  },
  waiting: {
    label: 'settings.notifyPage.me.kind.waiting.label',
    hint: 'settings.notifyPage.me.kind.waiting.hint',
  },
} as const satisfies Record<NotificationKind, { label: Key; hint: Key }>

const KINDS = Object.keys(KIND_TEXT) as NotificationKind[]

/** 只有管理員收得到的種類（後端也會把一般使用者的 `waiting` 剝掉）。 */
const ADMIN_ONLY_KINDS: ReadonlySet<NotificationKind> = new Set(['waiting'])

/** 每一種拒絕理由的一句話。少一種是編譯錯誤。 */
const REFUSAL_TEXT = {
  token_rejected: 'settings.notifyPage.refusal.token_rejected',
  discord_unreachable: 'settings.notifyPage.refusal.discord_unreachable',
  discord_id_invalid: 'settings.notifyPage.refusal.discord_id_invalid',
  bot_missing: 'settings.notifyPage.refusal.bot_missing',
  discord_id_missing: 'settings.notifyPage.refusal.discord_id_missing',
  berth_url_invalid: 'settings.notifyPage.refusal.berth_url_invalid',
} as const satisfies Record<NotifyRefusal, Key>

/** 這一頁是用哪個語言在看（通知就用它寫）。 */
function useUiLanguage(): Language {
  const { i18n } = useTranslation()
  return i18n.language === 'zh-Hant' ? 'zh-Hant' : 'en'
}

/**
 * 設定 → 通知（M4 票 123，`.scratch/m4/notify-settings-shape.md`）。它不是泊位：沒有泊位號、不在泊位板上。
 *
 * 兩半（M4 票 125）：管理員那一半是 Discord bot 與 Berth 的網址（一次性的設定）；每個人都有的那一半是
 * 我的通知（Discord ID 與要收的種類）與測試。**一般使用者只看得到後一半**，也沒有設定的分頁列——
 * 其他分頁他進不去（同 Overseerr：每個人的通知在自己的設定裡，管道的設定在管理員那邊）。
 */
export function NotifySettingsPage() {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)
  const admin = me.data?.role === 'admin'
  const mine = useQuery(myNotifyQueryOptions)

  return (
    <SettingsFrame
      tabs={admin}
      title={t('settings.notifyPage.title')}
      lede={t(admin ? 'settings.notifyPage.lede' : 'settings.notifyPage.userLede')}
    >
      {admin && <BotHalf />}
      {mine.data ? (
        <>
          <MySection mine={mine.data} admin={admin} />
          <TestSection mine={mine.data} admin={admin} />
        </>
      ) : mine.isError ? (
        <RequestFailed error={mine.error} lead={t('settings.notifyPage.readFailed')} />
      ) : (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      )}
    </SettingsFrame>
  )
}

/** 管理員那一半：bot 與 Berth 的網址，讀 `settings/notifications`。 */
function BotHalf() {
  const { t } = useTranslation()
  const bot = useQuery(botQueryOptions)
  if (bot.data)
    return (
      <>
        <BotSection bot={bot.data} />
        <BerthUrlSection bot={bot.data} />
      </>
    )
  if (bot.isError)
    return <RequestFailed error={bot.error} lead={t('settings.notifyPage.readFailed')} />
  return <p className="text-sm text-ink-dim">{t('health.checking')}</p>
}

/**
 * 存下 bot 之後把回來的狀態放進快取。「我的通知」那一份也帶著 bot 有沒有設定（測試鍵讀它），一起重讀。
 */
function useBotCache() {
  const queryClient = useQueryClient()
  return (next: NotifyBot) => {
    queryClient.setQueryData(botQueryOptions.queryKey, next)
    void queryClient.invalidateQueries({ queryKey: myNotifyQueryOptions.queryKey })
  }
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

function BotSection({ bot }: { bot: NotifyBot }) {
  const { t } = useTranslation()
  const cache = useBotCache()
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
            {bot.bot_configured ? (
              <>
                <span className="label bg-deck px-2 py-1.5 text-ink">
                  {t('settings.notifyPage.bot.configured')}
                </span>
                <span className="value wrap-anywhere">{bot.bot_name}</span>
              </>
            ) : (
              <span className="text-ink-dim">{t('settings.notifyPage.bot.unconfigured')}</span>
            )}
          </dd>
        </dl>

        {/* 管道因 token 被拒而停著（票 128）：換好 token 之後後端自己清掉，這一句跟著消失。 */}
        {bot.token_rejected && (
          <Notice signal="blocked" label={t('settings.notifyPage.bot.rejectedChip')}>
            {t('settings.notifyPage.bot.rejected')}
          </Notice>
        )}

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
              bot.bot_configured
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

        {bot.bot_configured && bot.invite_url && <Invite url={bot.invite_url} />}

        {bot.bot_configured && (
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

/**
 * Berth 從外面看的網址（M4 票 124）：通知裡的連結照它組。容器裡猜不出來，所以沒存過時預填瀏覽器
 * 現在開著的 origin——那是管理員打得開 Berth 的一個網址——但按了儲存才算數，在那之前通知不附連結。
 * 不是 http(s) 的完整網址由後端擋（422），說不行的是欄位自己。
 */
function BerthUrlSection({ bot }: { bot: NotifyBot }) {
  const { t } = useTranslation()
  const cache = useBotCache()
  // `null` 是「這一輪還沒動過」，那時欄位跟著存的值走（同 Jellyfin 的對外網址）。
  const [draft, setDraft] = useState<string | null>(null)
  const value = draft ?? (bot.berth_url || window.location.origin)
  const save = useMutation({
    mutationFn: () => saveBerthUrl(value),
    onSuccess: (next) => {
      cache(next)
      setDraft(null)
    },
  })
  const invalid = notifyRefusalOf(save.error)?.reason === 'berth_url_invalid'

  return (
    <SettingsSection
      id="notify-berth-url"
      title={t('settings.notifyPage.berth.title')}
      lede={t('settings.notifyPage.berth.lede')}
    >
      <form
        noValidate
        className="grid gap-3 sm:max-w-md"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <Field
          label={t('settings.notifyPage.berth.label')}
          type="url"
          inputMode="url"
          autoComplete="off"
          value={value}
          placeholder={t('settings.notifyPage.berth.placeholder')}
          hint={
            bot.berth_url
              ? t('settings.notifyPage.berth.set', { url: bot.berth_url })
              : t('settings.notifyPage.berth.unsaved')
          }
          error={invalid ? t(REFUSAL_TEXT.berth_url_invalid) : undefined}
          onChange={(event) => {
            setDraft(event.target.value)
            save.reset()
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <GhostButton type="submit" busy={save.isPending}>
            {t(
              save.isPending
                ? 'settings.notifyPage.berth.saving'
                : 'settings.notifyPage.berth.save',
            )}
          </GhostButton>
          <p aria-live="polite" className="text-xs text-ink-dim">
            {save.isSuccess ? t('settings.notifyPage.berth.saved') : ''}
          </p>
        </div>
        {save.isError && !invalid && (
          <Failed error={save.error} lead={t('settings.notifyPage.berth.failed')} />
        )}
      </form>
    </SettingsSection>
  )
}

/**
 * 我的通知：Discord ID 與要收的種類，同一個儲存鍵（M4 票 125）。存的那一刻順手記下介面語言。
 * 每個人都有這一段；`admin` 只決定補法說「你自己換」還是「找管理員」。
 */
function MySection({ mine, admin }: { mine: MyNotify; admin: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const language = useUiLanguage()
  const [id, setId] = useState(mine.discord_user_id)
  const [kinds, setKinds] = useState<ReadonlySet<NotificationKind>>(() => new Set(mine.kinds))
  const shownKinds = KINDS.filter((kind) => admin || !ADMIN_ONLY_KINDS.has(kind))
  const save = useMutation({
    mutationFn: () =>
      saveMine({
        discord_user_id: id.trim(),
        language,
        kinds: shownKinds.filter((kind) => kinds.has(kind)),
      }),
    onSuccess: (next) => queryClient.setQueryData(myNotifyQueryOptions.queryKey, next),
  })
  const invalid = notifyRefusalOf(save.error)?.reason === 'discord_id_invalid'
  const name = (code: Language) => t(`settings.notifyPage.languageName.${code}`)
  const unreachable = FAILURE_TEXT.recipient_unreachable

  function toggle(kind: NotificationKind, on: boolean) {
    setKinds((current) => {
      const next = new Set(current)
      if (on) next.add(kind)
      else next.delete(kind)
      return next
    })
    save.reset()
  }

  return (
    <SettingsSection id="notify-me" title={t('settings.notifyPage.me.title')}>
      {/* 上一則送給你的通知到不了（票 128）：原因記在這個人身上，補好後按測試送到了就收掉。 */}
      {mine.unreachable_at !== null && (
        <div className="mb-4">
          <Notice signal="blocked" label={t('settings.notifyPage.me.unreachableChip')}>
            <span className="grid gap-1">
              <span>
                {t('settings.notifyPage.me.unreachable')}
                {/* 時間與句子之間隔一個點：「沒送到」直接接「1 秒前」會黏成一句。 */}
                <span className="text-ink-dim">
                  {' · '}
                  <Timestamp at={mine.unreachable_at} past />
                </span>
              </span>
              <span>{t(unreachable.what)}</span>
              <span>{t(admin ? unreachable.fix : unreachable.userFix)}</span>
              <span>
                {t('settings.notifyPage.me.unreachableRetry', {
                  button: t('settings.notifyPage.test.send'),
                })}
              </span>
            </span>
          </Notice>
          <TechnicalDetails lines={[mine.unreachable_detail]} />
        </div>
      )}
      <form
        noValidate
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <div className="grid gap-3">
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
          {mine.bot_configured && mine.bot_name && (
            <p className="max-w-prose text-xs text-ink-dim">
              {t('settings.notifyPage.me.from', { bot: mine.bot_name })}
            </p>
          )}
        </div>
        <fieldset className="grid gap-3">
          <legend className="label mb-2 text-ink-dim">{t('settings.notifyPage.me.kinds')}</legend>
          {shownKinds.map((kind) => (
            <Checkbox
              key={kind}
              label={t(KIND_TEXT[kind].label)}
              hint={t(KIND_TEXT[kind].hint)}
              checked={kinds.has(kind)}
              onChange={(on) => toggle(kind, on)}
            />
          ))}
        </fieldset>
        <p className="max-w-prose text-xs text-ink-dim">
          {t('settings.notifyPage.me.language', { language: name(language) })}
          {mine.discord_user_id && mine.language !== language && (
            <> {t('settings.notifyPage.me.savedLanguage', { language: name(mine.language) })}</>
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

function TestSection({ mine, admin }: { mine: MyNotify; admin: boolean }) {
  const { t } = useTranslation()
  const missingId = mine.discord_user_id === ''
  const missingBot = !mine.bot_configured
  // 一般使用者補不了 bot：缺 bot 時只說「管理員還沒設定」，不叫他去做他做不了的事。
  const missing = missingBot
    ? admin
      ? missingId
        ? 'settings.notifyPage.test.missingBoth'
        : 'settings.notifyPage.test.missingBot'
      : 'settings.notifyPage.test.missingBotUser'
    : missingId
      ? 'settings.notifyPage.test.missingId'
      : null
  const queryClient = useQueryClient()
  // 成敗都重讀：送到了，「我的通知」上那一句要收掉；送不到，它要出現（後端在測試時設上或清掉）。
  // 管理員那一半的「已暫停」也可能跟著變（測試時 token 被拒）。
  const test = useMutation({
    mutationFn: sendTestMessage,
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: myNotifyQueryOptions.queryKey })
      if (admin) await queryClient.invalidateQueries({ queryKey: botQueryOptions.queryKey })
    },
  })
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
          {test.data && <TestResult result={test.data} admin={admin} />}
          {test.isError && (
            <Failed error={test.error} lead={t('settings.notifyPage.test.failed')} />
          )}
        </div>
      </div>
    </SettingsSection>
  )
}

function TestResult({ result, admin }: { result: NotifyTest; admin: boolean }): ReactNode {
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
              ? t(admin ? text.fix : text.userFix)
              : t('settings.notifyPage.test.failure.rate_limited.fix', { count: Math.ceil(wait) })}
          </span>
        </span>
      </Notice>
      <TechnicalDetails lines={[result.failure, result.detail]} />
    </>
  )
}

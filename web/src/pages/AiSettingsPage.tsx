import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  aiQueryOptions,
  aiRefusalOf,
  forgetAiKey,
  saveAi,
  testAi,
  type AiEndpoint,
  type AiProbeFailure,
  type AiProvider,
  type AiRefusal,
  type AiSecret,
  type AiSettings,
  type AiTest,
} from '../api/ai'
import {
  Checkbox,
  ConfirmAction,
  FILTER,
  FILTER_ACTIVE,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { priceSourceText } from '../usage/prices'

type Key = ParseKeys

const PROVIDERS: readonly AiProvider[] = ['anthropic', 'openai']

/** 每一種接口的名字與兩句提示。少一種是編譯錯誤。 */
const PROVIDER_TEXT = {
  anthropic: {
    name: 'settings.aiPage.provider.anthropic',
    hint: 'settings.aiPage.provider.hint.anthropic',
    baseUrl: 'settings.aiPage.baseUrl.hint.anthropic',
  },
  openai: {
    name: 'settings.aiPage.provider.openai',
    hint: 'settings.aiPage.provider.hint.openai',
    baseUrl: 'settings.aiPage.baseUrl.hint.openai',
  },
} as const satisfies Record<AiProvider, { name: Key; hint: Key; baseUrl: Key }>

/** base URL 留空時打的官方端點（`adapters.ai.OFFICIAL_BASE_URL`），當 placeholder 給人看。 */
const OFFICIAL_BASE_URL: Record<AiProvider, string> = {
  anthropic: 'https://api.anthropic.com',
  openai: 'https://api.openai.com/v1',
}

/** 測試沒成功的每一種：人話與補法。少一種是編譯錯誤。 */
const FAILURE_TEXT = {
  key_rejected: {
    what: 'settings.aiPage.test.failure.key_rejected.what',
    fix: 'settings.aiPage.test.failure.key_rejected.fix',
  },
  not_found: {
    what: 'settings.aiPage.test.failure.not_found.what',
    fix: 'settings.aiPage.test.failure.not_found.fix',
  },
  service_error: {
    what: 'settings.aiPage.test.failure.service_error.what',
    fix: 'settings.aiPage.test.failure.service_error.fix',
  },
  unreachable: {
    what: 'settings.aiPage.test.failure.unreachable.what',
    fix: 'settings.aiPage.test.failure.unreachable.fix',
  },
  bad_response: {
    what: 'settings.aiPage.test.failure.bad_response.what',
    fix: 'settings.aiPage.test.failure.bad_response.fix',
  },
} as const satisfies Record<AiProbeFailure, { what: Key; fix: Key }>

/** 拒絕理由的一句話。少一種是編譯錯誤。 */
const REFUSAL_TEXT = {
  base_url_invalid: 'settings.aiPage.refusal.base_url_invalid',
  key_missing: 'settings.aiPage.refusal.key_missing',
  model_missing: 'settings.aiPage.refusal.model_missing',
} as const satisfies Record<AiRefusal, Key>

/** 一種接口在表單上的樣子。key 欄只放這次貼上的，空著是「不動」。 */
type Draft = { base_url: string; model: string; api_key: string }

function draftOf(endpoint: AiEndpoint): Draft {
  return { base_url: endpoint.base_url, model: endpoint.model, api_key: '' }
}

/**
 * 設定 → AI（M5 票 09，`.scratch/m5/ai-settings-shape.md`）。不是泊位，只有管理員進得來。
 *
 * 一張表單：開關、接口、選中那一種的三欄、測試連線、網路搜尋，最後一顆「儲存」。兩種接口各自記著
 * 自己的值，切換時換成那一種存著的；儲存把選中的那一種設成現在用的。
 */
export function AiSettingsPage() {
  const { t } = useTranslation()
  const ai = useQuery(aiQueryOptions)

  return (
    <SettingsFrame title={t('settings.aiPage.title')} lede={t('settings.aiPage.lede')}>
      {ai.data ? (
        <AiForm saved={ai.data} />
      ) : ai.isError ? (
        <RequestFailed error={ai.error} lead={t('settings.aiPage.readFailed')} />
      ) : (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      )}
    </SettingsFrame>
  )
}

function AiForm({ saved }: { saved: AiSettings }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [enabled, setEnabled] = useState(saved.enabled)
  const [provider, setProvider] = useState<AiProvider>(saved.provider)
  const [drafts, setDrafts] = useState<Record<AiProvider, Draft>>({
    anthropic: draftOf(saved.anthropic),
    openai: draftOf(saved.openai),
  })
  const [tavily, setTavily] = useState('')
  /** 最後一次被拒的理由，標在它說的那一格；改了那一格就收掉。 */
  const [refused, setRefused] = useState<{ reason: AiRefusal; detail: string } | null>(null)
  /** 鍵下那一行說的是最後一個動作。 */
  const [status, setStatus] = useState<'saved' | 'removed' | null>(null)
  const draft = drafts[provider]
  const endpoint = saved[provider]
  const modelsId = useId()

  const save = useMutation({
    mutationFn: saveAi,
    onSuccess: (next) => {
      queryClient.setQueryData(aiQueryOptions.queryKey, next)
      // 存的那一種換成後端存下的樣子（Anthropic 的 /v1 已拿掉）；key 只寫不讀，欄位回到空的、
      // placeholder 改說「已設定」。另一種接口沒存的草稿留著。
      setDrafts((was) => ({ ...was, [next.provider]: draftOf(next[next.provider]) }))
      setTavily('')
      setStatus('saved')
    },
    onError: (error) => setRefused(aiRefusalOf(error)),
  })
  const test = useMutation({
    mutationFn: testAi,
    onError: (error) => setRefused(aiRefusalOf(error)),
  })

  function edit(change: Partial<Draft>, clears: AiRefusal) {
    setDrafts((was) => ({ ...was, [provider]: { ...was[provider], ...change } }))
    if (refused?.reason === clears) setRefused(null)
    test.reset()
    setStatus(null)
  }

  /**
   * 清掉一把 key 之後：清的是現在用的那一種時後端一併關掉了 AI，開關跟著它。只在後端真的從開變關時改，
   * 剛勾、還沒存的「開啟」不因為清了一把無關的 key 被取消。
   */
  function forgotten(next: AiSettings) {
    queryClient.setQueryData(aiQueryOptions.queryKey, next)
    if (saved.enabled && !next.enabled) setEnabled(false)
    setStatus('removed')
  }

  const form = {
    provider,
    base_url: draft.base_url,
    model: draft.model,
    api_key: draft.api_key.trim() || null,
  }
  const errorOf = (reason: AiRefusal) =>
    refused?.reason === reason ? t(REFUSAL_TEXT[reason]) : undefined

  return (
    <form
      noValidate
      className="grid gap-8"
      onSubmit={(event) => {
        event.preventDefault()
        setRefused(null)
        save.mutate({ ...form, enabled, tavily_api_key: tavily.trim() || null })
      }}
    >
      <SettingsSection
        id="ai-service"
        title={t('settings.aiPage.service.title')}
        lede={t('settings.aiPage.service.lede')}
      >
        <div className="grid gap-5">
          <Checkbox
            label={t('settings.aiPage.enabled.label')}
            hint={t('settings.aiPage.enabled.hint')}
            checked={enabled}
            onChange={(next) => {
              setEnabled(next)
              setStatus(null)
              if (refused?.reason !== 'base_url_invalid') setRefused(null)
            }}
          />

          <ProviderChoice
            provider={provider}
            inUse={saved.provider}
            onChange={(next) => {
              setProvider(next)
              setRefused(null)
              test.reset()
              setStatus(null)
            }}
          />

          <Field
            label={t('settings.aiPage.baseUrl.label')}
            value={draft.base_url}
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder={OFFICIAL_BASE_URL[provider]}
            hint={t(PROVIDER_TEXT[provider].baseUrl)}
            error={errorOf('base_url_invalid')}
            onChange={(event) => edit({ base_url: event.target.value }, 'base_url_invalid')}
          />

          <div className="grid gap-2">
            <PasswordField
              label={t('settings.aiPage.key.label')}
              value={draft.api_key}
              autoComplete="off"
              placeholder={t(
                endpoint.has_key
                  ? 'settings.aiPage.key.placeholderSet'
                  : 'settings.aiPage.key.placeholder',
              )}
              hint={t('settings.aiPage.key.hint')}
              error={errorOf('key_missing')}
              onChange={(event) => edit({ api_key: event.target.value }, 'key_missing')}
            />
            {endpoint.has_key && (
              <ForgetKey
                secret={provider}
                onDone={forgotten}
                label={t('settings.aiPage.key.remove')}
                warning={t(
                  saved.enabled && saved.provider === provider
                    ? 'settings.aiPage.key.removeWarningInUse'
                    : 'settings.aiPage.key.removeWarning',
                )}
              />
            )}
          </div>

          <div className="grid gap-2">
            <Field
              label={t('settings.aiPage.model.label')}
              value={draft.model}
              list={modelsId}
              autoComplete="off"
              spellCheck={false}
              hint={t('settings.aiPage.model.hint')}
              error={errorOf('model_missing')}
              onChange={(event) => edit({ model: event.target.value }, 'model_missing')}
            />
            <datalist id={modelsId}>
              {endpoint.known_models.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
            <Price endpoint={endpoint} model={draft.model} baseUrl={draft.base_url} />
          </div>

          <div className="grid gap-2">
            <p className="text-xs text-ink-dim">{t('settings.aiPage.test.hint')}</p>
            <div className="justify-self-start">
              <GhostButton
                type="button"
                busy={test.isPending}
                onClick={() => {
                  setRefused(null)
                  test.mutate(form)
                }}
              >
                {t(test.isPending ? 'settings.aiPage.test.testing' : 'settings.aiPage.test.button')}
              </GhostButton>
            </div>
            {/* 一直掛著：跟著結果一起掛上去的 live region 多數閱讀器不念（M3 票 06）。 */}
            <div aria-live="polite" className="grid gap-1">
              {test.data && <TestResult result={test.data} />}
              {test.isError && aiRefusalOf(test.error) === null && (
                <RequestFailed error={test.error} lead={t('settings.aiPage.test.didNotRun')} />
              )}
            </div>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        id="ai-search"
        title={t('settings.aiPage.search.title')}
        lede={t('settings.aiPage.search.lede')}
      >
        <div className="grid gap-3">
          <PasswordField
            label={t('settings.aiPage.search.label')}
            value={tavily}
            autoComplete="off"
            placeholder={t(
              saved.has_tavily_key
                ? 'settings.aiPage.key.placeholderSet'
                : 'settings.aiPage.key.placeholder',
            )}
            onChange={(event) => {
              setTavily(event.target.value)
              setStatus(null)
            }}
          />
          {saved.has_tavily_key && (
            <ForgetKey
              secret="tavily"
              onDone={forgotten}
              label={t('settings.aiPage.search.remove')}
              warning={t('settings.aiPage.search.removeWarning')}
            />
          )}
        </div>
      </SettingsSection>

      <div className="grid gap-2">
        <div className="sm:max-w-xs">
          <PrimaryButton type="submit" busy={save.isPending}>
            {t(save.isPending ? 'settings.aiPage.save.saving' : 'settings.aiPage.save.button')}
          </PrimaryButton>
        </div>
        {save.isError && aiRefusalOf(save.error) === null && (
          <RequestFailed error={save.error} lead={t('settings.aiPage.save.failed')} />
        )}
        <p role="status" className="text-xs text-ink-dim">
          {status === 'saved'
            ? t('settings.aiPage.save.saved')
            : status === 'removed'
              ? t('settings.aiPage.key.removed')
              : ''}
        </p>
      </div>
    </form>
  )
}

/** 兩顆 `aria-pressed` 的切換鍵（同篩選列的方塊）。 */
function ProviderChoice({
  provider,
  inUse,
  onChange,
}: {
  provider: AiProvider
  inUse: AiProvider
  onChange: (next: AiProvider) => void
}) {
  const { t } = useTranslation()
  const labelId = useId()
  const hintId = useId()

  return (
    <div className="grid gap-2">
      <p id={labelId} className="label text-ink-dim">
        {t('settings.aiPage.provider.label')}
      </p>
      <div
        role="group"
        aria-labelledby={labelId}
        aria-describedby={hintId}
        className="flex flex-wrap gap-2"
      >
        {PROVIDERS.map((each) => (
          <button
            key={each}
            type="button"
            aria-pressed={each === provider}
            onClick={() => onChange(each)}
            className={`${each === provider ? FILTER_ACTIVE : FILTER} normal-case`}
          >
            {t(PROVIDER_TEXT[each].name)}
          </button>
        ))}
      </div>
      <div id={hintId} className="grid gap-1 text-xs text-ink-dim">
        <p>{t(PROVIDER_TEXT[provider].hint)}</p>
        <p>{t('settings.aiPage.provider.inUse', { name: t(PROVIDER_TEXT[inUse].name) })}</p>
      </div>
    </div>
  )
}

/**
 * 已存的端點與模型的價目；查不到是「未知」，不當 0。價錢跟著端點走（M5 票 21b），所以表單上的模型或
 * base URL 改了還沒存時不猜。
 */
function Price({
  endpoint,
  model,
  baseUrl,
}: {
  endpoint: AiEndpoint
  model: string
  baseUrl: string
}) {
  const { t } = useTranslation()
  let body: ReactNode
  if (model.trim() !== endpoint.model || baseUrl.trim() !== endpoint.base_url)
    body = t('settings.aiPage.price.unsaved')
  else if (!endpoint.model) body = t('settings.aiPage.price.none')
  else if (endpoint.price === null) body = t('settings.aiPage.price.unknown')
  else
    body = (
      <>
        <span className="tabular-nums">
          {t('settings.aiPage.price.known', {
            input: endpoint.price.input,
            output: endpoint.price.output,
            cacheRead: endpoint.price.cache_read,
            cacheWrite: endpoint.price.cache_write,
          })}
        </span>{' '}
        <span className="text-ink-dim">{priceSourceText(t, endpoint.price.source)}</span>
      </>
    )

  return (
    <p className="text-xs text-ink">
      <span className="label mr-2 text-ink-dim">{t('settings.aiPage.price.label')}</span> {body}
    </p>
  )
}

function TestResult({ result }: { result: AiTest }) {
  const { t } = useTranslation()
  if (result.ok || result.failure === null) {
    return (
      <Notice signal="secured" label={t('settings.aiPage.test.ok')}>
        {t('settings.aiPage.test.answeredBy')}{' '}
        <span className="value wrap-anywhere">{result.model}</span>
      </Notice>
    )
  }
  const text = FAILURE_TEXT[result.failure]
  return (
    <>
      <Notice signal="blocked" label={t('common.failed')}>
        <span className="grid gap-1">
          <span>{t(text.what)}</span>
          <span>{t(text.fix)}</span>
        </span>
      </Notice>
      <TechnicalDetails
        lines={[
          result.status === null ? result.failure : `HTTP ${result.status} · ${result.failure}`,
          result.detail,
        ]}
      />
    </>
  )
}

/** 「移除 key」：就地二次確認，確認才清。 */
function ForgetKey({
  secret,
  label,
  warning,
  onDone,
}: {
  secret: AiSecret
  label: string
  warning: string
  onDone: (next: AiSettings) => void
}) {
  const { t } = useTranslation()
  const forget = useMutation({ mutationFn: () => forgetAiKey(secret), onSuccess: onDone })

  return (
    <div className="grid justify-items-start gap-2">
      <ConfirmAction
        label={label}
        confirmLabel={t('settings.aiPage.key.removeConfirm')}
        pendingLabel={t('settings.aiPage.key.removing')}
        pending={forget.isPending}
        warning={warning}
        onConfirm={() => forget.mutate()}
      />
      {forget.isError && (
        <RequestFailed error={forget.error} lead={t('settings.aiPage.save.failed')} />
      )}
    </div>
  )
}

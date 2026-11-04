import { useId, useState, type ReactNode } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  aiQueryOptions,
  aiReasoningQueryOptions,
  aiRefusalOf,
  aiSuggestionsQueryOptions,
  fetchAiModels,
  forgetAiKey,
  saveAi,
  testAi,
  type AiEndpoint,
  type AiModels,
  type AiProbeFailure,
  type AiProvider,
  type AiReasoning,
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
import { useDebounced } from '../components/useDebounced'
import { useHashTarget } from '../components/useHashTarget'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { priceSourceText } from '../usage/prices'

type Key = ParseKeys

/** 打網址時等這麼久才查建議：查的是本機表、不連外，只是不必每個按鍵都問一次。 */
const SUGGEST_DEBOUNCE_MS = 300

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

/**
 * 「取得模型」沒問到的每一種（M5.5 票 02）。與測試連線不同的是 `not_found`：列模型時那是這個端點沒有
 * 模型清單（DeepSeek 的 Anthropic 接口就是，brief §20.26），不是模型名或網址打錯。少一種是編譯錯誤。
 */
const MODELS_FAILURE_TEXT = {
  key_rejected: 'settings.aiPage.test.failure.key_rejected.what',
  not_found: 'settings.aiPage.models.noList',
  service_error: 'settings.aiPage.test.failure.service_error.what',
  unreachable: 'settings.aiPage.test.failure.unreachable.what',
  bad_response: 'settings.aiPage.test.failure.bad_response.what',
} as const satisfies Record<AiProbeFailure, Key>

/** 拒絕理由的一句話。少一種是編譯錯誤。 */
const REFUSAL_TEXT = {
  base_url_invalid: 'settings.aiPage.refusal.base_url_invalid',
  key_missing: 'settings.aiPage.refusal.key_missing',
  model_missing: 'settings.aiPage.refusal.model_missing',
} as const satisfies Record<AiRefusal, Key>

/** 推理程度由少到多（M5.5 票 17）。沒有「預設」這一級（使用者定），沒設過是 `medium`。少一種是編譯錯誤。 */
const REASONING_TEXT = {
  off: 'settings.aiPage.reasoning.off',
  low: 'settings.aiPage.reasoning.low',
  medium: 'settings.aiPage.reasoning.medium',
  high: 'settings.aiPage.reasoning.high',
} as const satisfies Record<AiReasoning, Key>

const REASONING_LEVELS = Object.keys(REASONING_TEXT) as AiReasoning[]

function isReasoning(value: string): value is AiReasoning {
  return value in REASONING_TEXT
}

/** 一種接口在表單上的樣子。key 欄只放這次貼上的，空著是「不動」。 */
type Draft = { base_url: string; model: string; api_key: string; reasoning: AiReasoning }

function draftOf(endpoint: AiEndpoint): Draft {
  return {
    base_url: endpoint.base_url,
    model: endpoint.model,
    api_key: '',
    reasoning: endpoint.reasoning,
  }
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
  // 停下的說明連到 `#ai-reasoning`（M5.5 票 17）：表單是讀到設定才畫的，原生的錨點捲動已經錯過。
  useHashTarget(true)

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
  /** 「取得模型」（M5.5 票 02）：base URL、key 或接口一改就收掉，問的已經不是這個端點。 */
  const fetched = useMutation({
    mutationFn: fetchAiModels,
    onError: (error) => setRefused(aiRefusalOf(error)),
  })
  const suggestFor = useDebounced(draft.base_url.trim(), SUGGEST_DEBOUNCE_MS)
  const suggested = useQuery({
    ...aiSuggestionsQueryOptions(provider, suggestFor),
    // 換網址時舊的建議留到新的回來，清單不閃空。
    placeholderData: keepPreviousData,
  })
  const models = fetched.data?.models ?? suggested.data?.models ?? []

  function edit(change: Partial<Draft>, ...clears: AiRefusal[]) {
    setDrafts((was) => ({ ...was, [provider]: { ...was[provider], ...change } }))
    if (refused && clears.includes(refused.reason)) setRefused(null)
    test.reset()
    if (change.base_url !== undefined || change.api_key !== undefined) fetched.reset()
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
  // 存著 key 還說沒有 key，只會是網址改了：存著的那把只送到存它的端點（M5.5 票 01）。
  const keyError =
    refused?.reason === 'key_missing' && endpoint.has_key
      ? t('settings.aiPage.key.savedElsewhere')
      : errorOf('key_missing')

  return (
    <form
      noValidate
      className="grid gap-8"
      onSubmit={(event) => {
        event.preventDefault()
        setRefused(null)
        save.mutate({
          ...form,
          enabled,
          reasoning: draft.reasoning,
          tavily_api_key: tavily.trim() || null,
        })
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
              fetched.reset()
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
            // key_missing 也收：存著的 key 用不用得上看網址。
            onChange={(event) =>
              edit({ base_url: event.target.value }, 'base_url_invalid', 'key_missing')
            }
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
              error={keyError}
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
              {models.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
            <div className="justify-self-start">
              <GhostButton
                type="button"
                busy={fetched.isPending}
                onClick={() => {
                  setRefused(null)
                  fetched.mutate({
                    provider: form.provider,
                    base_url: form.base_url,
                    api_key: form.api_key,
                  })
                }}
              >
                {t(
                  fetched.isPending
                    ? 'settings.aiPage.models.fetching'
                    : 'settings.aiPage.models.button',
                )}
              </GhostButton>
            </div>
            <div aria-live="polite" className="grid gap-1">
              {fetched.data && <FetchedModels result={fetched.data} />}
              {fetched.isError && aiRefusalOf(fetched.error) === null && (
                <RequestFailed error={fetched.error} lead={t('settings.aiPage.models.didNotRun')} />
              )}
            </div>
            <Price endpoint={endpoint} model={draft.model} baseUrl={draft.base_url} />
          </div>

          <ReasoningLevel
            provider={provider}
            model={draft.model}
            value={draft.reasoning}
            onChange={(reasoning) => edit({ reasoning })}
          />

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
            // OpenAI 相容接口沒有伺服器端搜尋：沒有 key 就整個沒有網搜（票 23d）。
            hint={
              provider === 'openai' && !saved.has_tavily_key && !tavily.trim()
                ? t('settings.aiPage.search.needed')
                : undefined
            }
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
 * 推理程度（M5.5 票 17），模型欄下面一格。DeepSeek 只分低與高（brief §20.26），提示照實說；OpenAI
 * 接口上認不得的模型、沒有 effort 的 Claude，Berth 不送這個參數，說這個模型的程度沒有效果。下拉選單的
 * `id` 是停下的說明連過來的錨點（`#ai-reasoning`）：落在它身上，鍵盤使用者不必再按一次 Tab。
 */
function ReasoningLevel({
  provider,
  model,
  value,
  onChange,
}: {
  provider: AiProvider
  model: string
  value: AiReasoning
  onChange: (next: AiReasoning) => void
}) {
  const { t } = useTranslation()
  const id = 'ai-reasoning'
  const typed = useDebounced(model.trim(), SUGGEST_DEBOUNCE_MS)
  const applies = useQuery(aiReasoningQueryOptions(provider, typed))

  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="label text-ink-dim">
        {t('settings.aiPage.reasoning.label')}
      </label>
      <select
        id={id}
        aria-describedby={`${id}-hint`}
        value={value}
        onChange={(event) => {
          if (isReasoning(event.target.value)) onChange(event.target.value)
        }}
        className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink sm:max-w-xs"
      >
        {REASONING_LEVELS.map((level) => (
          <option key={level} value={level}>
            {t(REASONING_TEXT[level])}
          </option>
        ))}
      </select>
      <div id={`${id}-hint`} aria-live="polite" className="grid gap-1 text-xs text-ink-dim">
        <p>{t('settings.aiPage.reasoning.hint')}</p>
        {applies.data?.applies === false && <p>{t('settings.aiPage.reasoning.noEffect')}</p>}
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

/** 「取得模型」的結果：問到幾個，或為什麼沒問到、建議改用本機表。 */
function FetchedModels({ result }: { result: AiModels }) {
  const { t } = useTranslation()
  if (result.source === 'endpoint') {
    return (
      <p className="text-xs text-ink">
        {t('settings.aiPage.models.fetched', { count: result.models.length })}
      </p>
    )
  }
  if (result.failure === null) {
    return <p className="text-xs text-ink">{t('settings.aiPage.models.empty')}</p>
  }
  return (
    <>
      <Notice signal="blocked" label={t('settings.aiPage.models.failed')}>
        <span className="grid gap-1">
          <span>{t(MODELS_FAILURE_TEXT[result.failure])}</span>
          <span>{t('settings.aiPage.models.fallback')}</span>
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

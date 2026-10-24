import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  aiQueryOptions,
  aiRefusalOf,
  listAiModels,
  runAiTest,
  saveAi,
  type AiFailure,
  type AiProbeStep,
  type AiRefusal,
  type AiSettings,
  type AiTest,
  type AiToolTest,
  type ToolGap,
} from '../api/ai'
import {
  ConfirmAction,
  Field,
  GhostButton,
  Notice,
  PasswordField,
  PrimaryButton,
} from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'

type Key = ParseKeys

/**
 * 每一種失敗的人話與補法。少一種是編譯錯誤；`rate_limited` 的補法有秒數時另外挑（`FailureLines`）。
 */
const FAILURE_TEXT = {
  rate_limited: {
    what: 'settings.aiPage.test.failure.rate_limited.what',
    fix: 'settings.aiPage.test.failure.rate_limited.fixUnknown',
  },
  quota_exhausted: {
    what: 'settings.aiPage.test.failure.quota_exhausted.what',
    fix: 'settings.aiPage.test.failure.quota_exhausted.fix',
  },
  provider_down: {
    what: 'settings.aiPage.test.failure.provider_down.what',
    fix: 'settings.aiPage.test.failure.provider_down.fix',
  },
  auth_failed: {
    what: 'settings.aiPage.test.failure.auth_failed.what',
    fix: 'settings.aiPage.test.failure.auth_failed.fix',
  },
  model_not_found: {
    what: 'settings.aiPage.test.failure.model_not_found.what',
    fix: 'settings.aiPage.test.failure.model_not_found.fix',
  },
  unreachable: {
    what: 'settings.aiPage.test.failure.unreachable.what',
    fix: 'settings.aiPage.test.failure.unreachable.fix',
  },
  rejected: {
    what: 'settings.aiPage.test.failure.rejected.what',
    fix: 'settings.aiPage.test.failure.rejected.fix',
  },
} as const satisfies Record<AiFailure, { what: Key; fix: Key }>

/** 模型不支援工具呼叫時的每一種樣子，各一句。少一種是編譯錯誤。 */
const GAP_TEXT = {
  tools_rejected: 'settings.aiPage.gap.tools_rejected',
  written_as_text: 'settings.aiPage.gap.written_as_text',
  tools_ignored: 'settings.aiPage.gap.tools_ignored',
  wrong_call: 'settings.aiPage.gap.wrong_call',
  result_rejected: 'settings.aiPage.gap.result_rejected',
  no_reply: 'settings.aiPage.gap.no_reply',
} as const satisfies Record<ToolGap, Key>

/** tokens 表的列名。少一種是編譯錯誤。 */
const STEP_TEXT = {
  hello: 'settings.aiPage.test.usage.hello',
  tool_call: 'settings.aiPage.test.usage.tool_call',
  tool_result: 'settings.aiPage.test.usage.tool_result',
} as const satisfies Record<AiProbeStep, Key>

/** 每一種拒絕理由的一句話。少一種是編譯錯誤。 */
const REFUSAL_TEXT = {
  base_url_invalid: 'settings.aiPage.refusal.base_url_invalid',
  not_ready: 'settings.aiPage.refusal.not_ready',
} as const satisfies Record<AiRefusal, Key>

/** 設定 → AI（M5）。只有管理員：API key 與模型是整台 Berth 的設定。 */
export function AiSettingsPage() {
  const { t } = useTranslation()
  const ai = useQuery(aiQueryOptions)

  return (
    <SettingsFrame tabs title={t('settings.aiPage.title')} lede={t('settings.aiPage.lede')}>
      {ai.data ? (
        <AiBody ai={ai.data} />
      ) : ai.isError ? (
        <RequestFailed error={ai.error} lead={t('settings.aiPage.readFailed')} />
      ) : (
        <p className="text-sm text-ink-dim">{t('health.checking')}</p>
      )}
    </SettingsFrame>
  )
}

/** 一次命令沒成的那一格：後端說不行的用人話加原文，其餘照請求為什麼沒成說。 */
function Failed({ error, lead }: { error: unknown; lead: string }) {
  const { t } = useTranslation()
  const refusal = aiRefusalOf(error)
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

/** 一個 failure 的「發生什麼」與「怎麼補」，成兩行。 */
function FailureLines({ failure, retryAfter }: { failure: AiFailure; retryAfter: number | null }) {
  const { t } = useTranslation()
  return (
    <span className="grid gap-1">
      <span>{t(FAILURE_TEXT[failure].what)}</span>
      <span>
        {/* 限流有秒數就說秒數；沒有就說「等幾秒」。 */}
        {failure === 'rate_limited' && retryAfter !== null
          ? t('settings.aiPage.test.failure.rate_limited.fix', { count: Math.ceil(retryAfter) })
          : t(FAILURE_TEXT[failure].fix)}
      </span>
    </span>
  )
}

/**
 * 表單的草稿放在這一層：狀態要知道「改了格式、base URL 或模型還沒存」（後端存下時會清掉測試結論），
 * 測試也只打**存著的**設定，所以草稿沒存時要先存。
 */
function AiBody({ ai }: { ai: AiSettings }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [format, setFormat] = useState(ai.format)
  const [baseUrl, setBaseUrl] = useState(ai.base_url)
  const [model, setModel] = useState(ai.model)
  const [key, setKey] = useState('')
  const [options, setOptions] = useState<string[]>([])
  const formatId = useId()
  const listId = useId()
  const missingId = useId()
  const unsavedId = useId()

  const changed =
    format !== ai.format || baseUrl.trim() !== ai.base_url || model.trim() !== ai.model
  const dirty = changed || key.trim() !== ''
  const official = baseUrl.trim() === ''

  const save = useMutation({
    mutationFn: () =>
      saveAi({
        format,
        base_url: baseUrl.trim(),
        model: model.trim(),
        // 只有真的輸入了才帶 key：空字串在後端是「清掉」，那件事只走「移除 key」。
        api_key: key.trim() === '' ? null : key.trim(),
      }),
    onSuccess: (next) => {
      queryClient.setQueryData(aiQueryOptions.queryKey, next)
      // 後端可能把網址整理過；欄位回到存著的值，才不會一直顯示「改了還沒存」。
      setFormat(next.format)
      setBaseUrl(next.base_url)
      setModel(next.model)
      setKey('')
      remove.reset()
    },
  })
  const remove = useMutation({
    // 移除用存著的值，不帶欄位裡還沒存的草稿。
    mutationFn: () =>
      saveAi({ format: ai.format, base_url: ai.base_url, model: ai.model, api_key: '' }),
    onSuccess: (next) => {
      queryClient.setQueryData(aiQueryOptions.queryKey, next)
      save.reset()
    },
  })
  // 測試打的是存著的設定：表單有改動就先存，再測。
  const test = useMutation({
    mutationFn: async () => {
      if (dirty) await save.mutateAsync()
      return runAiTest()
    },
    // 成敗都重讀：狀態裡的工具結論要跟著變。
    onSettled: () => queryClient.invalidateQueries({ queryKey: aiQueryOptions.queryKey }),
  })
  const models = useMutation({
    mutationFn: listAiModels,
    onSuccess: (next) => setOptions(next.models ?? []),
  })

  const missing: Key | null = official
    ? ai.api_key_present || key.trim() !== ''
      ? null
      : 'settings.aiPage.connection.missingKey'
    : model.trim() === ''
      ? 'settings.aiPage.connection.missingModel'
      : null

  const invalidUrl = aiRefusalOf(save.error)?.reason === 'base_url_invalid'
  const modelHint =
    official && ai.default_model
      ? t('settings.aiPage.connection.modelHintDefault', { model: ai.default_model })
      : t(
          official
            ? 'settings.aiPage.connection.modelHintOfficial'
            : 'settings.aiPage.connection.modelHintThirdParty',
        )

  return (
    <>
      <SettingsSection id="ai-connection" title={t('settings.aiPage.connection.title')}>
        <form
          noValidate
          className="grid gap-4 sm:max-w-md"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate()
          }}
        >
          <p className="grid gap-2">
            <label htmlFor={formatId} className="label text-ink-dim">
              {t('settings.aiPage.connection.formatLabel')}
            </label>
            <select
              id={formatId}
              value={format}
              onChange={(event) => setFormat(event.target.value as typeof format)}
              className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
            >
              <option value="anthropic">{t('settings.aiPage.connection.formatAnthropic')}</option>
            </select>
          </p>
          <Field
            label={t('settings.aiPage.connection.baseUrlLabel')}
            type="url"
            inputMode="url"
            autoComplete="off"
            value={baseUrl}
            placeholder={t('settings.aiPage.connection.baseUrlPlaceholder')}
            hint={t('settings.aiPage.connection.baseUrlHint')}
            error={invalidUrl ? t(REFUSAL_TEXT.base_url_invalid) : undefined}
            onChange={(event) => {
              setBaseUrl(event.target.value)
              save.reset()
            }}
          />
          <PasswordField
            label={t('settings.aiPage.connection.keyLabel')}
            value={key}
            autoComplete="off"
            placeholder={t(
              ai.api_key_present
                ? 'settings.aiPage.connection.keyPlaceholderSet'
                : 'settings.aiPage.connection.keyPlaceholder',
            )}
            hint={t('settings.aiPage.connection.keyHint')}
            onChange={(event) => {
              setKey(event.target.value)
              save.reset()
            }}
          />
          <Field
            label={t('settings.aiPage.connection.modelLabel')}
            list={listId}
            autoComplete="off"
            value={model}
            placeholder={official ? (ai.default_model ?? '') : ''}
            hint={modelHint}
            onChange={(event) => {
              setModel(event.target.value)
              save.reset()
            }}
          />
          <datalist id={listId}>
            {options.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>

          <div className="grid justify-items-start gap-2">
            {/* 讀清單用的是存著的設定：有沒存的改動時鍵照樣在 Tab 順序上，說先儲存（同通知頁的測試鍵）。 */}
            <GhostButton
              type="button"
              busy={models.isPending || dirty}
              aria-describedby={dirty ? unsavedId : undefined}
              onClick={() => models.mutate()}
            >
              {t(
                models.isPending ? 'settings.aiPage.models.reading' : 'settings.aiPage.models.read',
              )}
            </GhostButton>
            {dirty && (
              <p id={unsavedId} className="text-xs text-ink-dim">
                {t('settings.aiPage.models.unsaved')}
              </p>
            )}
            <p aria-live="polite" className="text-xs text-ink-dim">
              {models.isSuccess
                ? models.data.failure !== null
                  ? ''
                  : models.data.models === null
                    ? t('settings.aiPage.models.none')
                    : t('settings.aiPage.models.found', { count: models.data.models.length })
                : ''}
            </p>
            {models.isSuccess && models.data.failure !== null && (
              <div className="grid gap-1">
                <Notice signal="blocked" label={t('common.failed')}>
                  <FailureLines failure={models.data.failure} retryAfter={null} />
                </Notice>
                <TechnicalDetails lines={[models.data.failure, models.data.detail]} />
              </div>
            )}
            {models.isError && (
              <Failed error={models.error} lead={t('settings.aiPage.models.failed')} />
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <GhostButton type="submit" busy={save.isPending && !test.isPending}>
              {t(
                save.isPending && !test.isPending
                  ? 'settings.aiPage.connection.saving'
                  : 'settings.aiPage.connection.save',
              )}
            </GhostButton>
            {/* 缺東西時鍵照樣在 Tab 順序上、念得出「不可用」與缺什麼，不是 `disabled`（`busy` 的理由）。 */}
            <PrimaryButton
              type="button"
              busy={test.isPending || missing !== null}
              aria-describedby={missing ? missingId : undefined}
              onClick={() => test.mutate()}
            >
              {t(
                test.isPending
                  ? 'settings.aiPage.connection.testing'
                  : 'settings.aiPage.connection.saveTest',
              )}
            </PrimaryButton>
          </div>
          {missing && (
            <p id={missingId} className="text-xs text-ink-dim">
              {t(missing)}
            </p>
          )}
          {save.isError && !invalidUrl && (
            <Failed error={save.error} lead={t('settings.aiPage.connection.failed')} />
          )}
          <p aria-live="polite" className="text-xs text-ink-dim">
            {save.isSuccess
              ? t('settings.aiPage.connection.saved')
              : remove.isSuccess
                ? t('settings.aiPage.connection.keyRemoved')
                : ''}
          </p>
        </form>

        {ai.api_key_present && (
          <div className="mt-4 grid justify-items-start gap-2">
            <ConfirmAction
              label={t('settings.aiPage.connection.remove')}
              confirmLabel={t('settings.aiPage.connection.removeConfirm')}
              pendingLabel={t('settings.aiPage.connection.removing')}
              pending={remove.isPending}
              warning={t('settings.aiPage.connection.removeWarning')}
              onConfirm={() => remove.mutate()}
            />
            {remove.isError && (
              <Failed error={remove.error} lead={t('settings.aiPage.connection.failed')} />
            )}
          </div>
        )}
      </SettingsSection>

      <StatusSection ai={ai} changed={changed} />

      <SettingsSection id="ai-test" title={t('settings.aiPage.test.title')}>
        {/* live region 常駐、結果放進去：跟結果同一次掛上的話不會被念出來。 */}
        <div aria-live="polite" aria-busy={test.isPending} className="grid gap-2">
          {test.isPending && (
            <p className="text-sm text-ink-dim">{t('settings.aiPage.test.running')}</p>
          )}
          {test.data && !test.isPending && <TestResult result={test.data} />}
          {test.isError && !save.isError && (
            <Failed error={test.error} lead={t('settings.aiPage.test.failed')} />
          )}
        </div>
      </SettingsSection>
    </>
  )
}

function StatusSection({ ai, changed }: { ai: AiSettings; changed: boolean }) {
  const { t } = useTranslation()
  const tools = ai.tool_test
  // 改了還沒存：舊的結論不再是現況，存下時後端也會清掉它。
  const chatOnly = !changed && tools !== null && !tools.supported

  return (
    <SettingsSection id="ai-status" title={t('settings.aiPage.status.title')}>
      <div className="grid gap-4">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[max-content_minmax(0,1fr)]">
          <dt className="label text-ink-dim">{t('settings.aiPage.status.config')}</dt>
          <dd className="flex flex-wrap items-center gap-2 text-sm text-ink">
            {ai.ready ? (
              <span className="label bg-deck px-2 py-1.5 text-ink">
                {t('settings.aiPage.status.ready')}
              </span>
            ) : (
              <>
                <span className="text-ink-dim">{t('settings.aiPage.status.notReady')}</span>
                <span className="text-xs text-ink-dim">
                  {t('settings.aiPage.status.notReadyHint')}
                </span>
              </>
            )}
          </dd>
          <dt className="label text-ink-dim">{t('settings.aiPage.status.tools')}</dt>
          <dd className="text-sm text-ink">
            {changed ? (
              <span className="text-ink-dim">{t('settings.aiPage.status.changed')}</span>
            ) : tools === null ? (
              <span className="text-ink-dim">{t('settings.aiPage.status.untested')}</span>
            ) : tools.supported ? (
              <span className="label bg-deck px-2 py-1.5 text-ink">
                {t('settings.aiPage.status.supported')}
              </span>
            ) : (
              <span className="grid gap-1">
                <span className="label">{t('settings.aiPage.status.chatOnly')}</span>
                {tools.gap && <span>{t(GAP_TEXT[tools.gap])}</span>}
              </span>
            )}
          </dd>
        </dl>
        {chatOnly && (
          <div className="grid gap-1">
            {/* 存著的狀態，不是剛發生的錯：不用 blocked（它是 role=alert，每次開頁都會被念出來）。
                換不換模型是管理員的決定，所以是 assigned。 */}
            <Notice signal="assigned" label={t('settings.aiPage.status.chatOnlyChip')}>
              {t('settings.aiPage.status.chatOnlyNotice')}
            </Notice>
            <ToolsDetails tools={tools} />
          </div>
        )}
      </div>
    </SettingsSection>
  )
}

function ToolsDetails({ tools }: { tools: AiToolTest }) {
  return <TechnicalDetails lines={[tools.gap, tools.detail]} />
}

function TestResult({ result }: { result: AiTest }): ReactNode {
  const { t } = useTranslation()
  return (
    <>
      {result.failure !== null ? (
        <div className="grid gap-1">
          <Notice signal="blocked" label={t('common.failed')}>
            <FailureLines failure={result.failure} retryAfter={result.retry_after} />
          </Notice>
          <TechnicalDetails lines={[result.failure, result.detail]} />
        </div>
      ) : (
        <>
          <Notice signal="secured" label={t('settings.aiPage.test.connected')}>
            {result.reply && (
              <span className="wrap-anywhere">
                {t('settings.aiPage.test.reply', { reply: result.reply })}
              </span>
            )}
          </Notice>
          {result.tools ? (
            <div className="grid gap-1">
              <Notice
                signal={result.tools.supported ? 'secured' : 'blocked'}
                label={t('settings.aiPage.test.toolsLabel')}
              >
                {result.tools.supported ? (
                  t('settings.aiPage.test.toolsSupported')
                ) : (
                  <span className="grid gap-1">
                    <span>{t('settings.aiPage.test.toolsChatOnly')}</span>
                    {result.tools.gap && <span>{t(GAP_TEXT[result.tools.gap])}</span>}
                  </span>
                )}
              </Notice>
              <ToolsDetails tools={result.tools} />
            </div>
          ) : (
            <div className="grid gap-1">
              <Notice signal="neutral" label={t('settings.aiPage.test.toolsLabel')}>
                <span className="grid gap-1">
                  <span>{t('settings.aiPage.test.toolsNotTested')}</span>
                  {result.tools_failure && (
                    <FailureLines failure={result.tools_failure} retryAfter={null} />
                  )}
                </span>
              </Notice>
              <TechnicalDetails lines={[result.tools_failure, result.tools_detail]} />
            </div>
          )}
        </>
      )}
      {result.calls.length > 0 && <UsageTable calls={result.calls} />}
    </>
  )
}

/** 每一次請求的 tokens。後端不知道的是 `null`，說「不知道」，不是 0。 */
function UsageTable({ calls }: { calls: AiTest['calls'] }) {
  const { t, i18n } = useTranslation()
  const number = (value: number | null) =>
    value === null
      ? t('settings.aiPage.test.usage.unknown')
      : new Intl.NumberFormat(i18n.language).format(value)

  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full border-collapse border-2 border-rule bg-well text-left">
        <caption className="label px-4 py-2 text-left text-ink-dim">
          {t('settings.aiPage.test.usage.title')}
        </caption>
        <thead>
          <tr>
            <th scope="col" className="label px-4 py-2 text-ink-dim">
              {t('settings.aiPage.test.usage.step')}
            </th>
            {(['input', 'output', 'cacheWrite', 'cacheRead'] as const).map((column) => (
              <th key={column} scope="col" className="label px-4 py-2 text-right text-ink-dim">
                {t(`settings.aiPage.test.usage.${column}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calls.map((call) => (
            <tr key={call.step} className="border-t-2 border-rule">
              <th scope="row" className="px-4 py-2 text-sm font-normal text-ink">
                {t(STEP_TEXT[call.step])}
              </th>
              <td className="value px-4 py-2 text-right text-sm">
                {number(call.usage.input_tokens)}
              </td>
              <td className="value px-4 py-2 text-right text-sm">
                {number(call.usage.output_tokens)}
              </td>
              <td className="value px-4 py-2 text-right text-sm">
                {number(call.usage.cache_write_tokens)}
              </td>
              <td className="value px-4 py-2 text-right text-sm">
                {number(call.usage.cache_read_tokens)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

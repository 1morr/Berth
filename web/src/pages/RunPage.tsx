import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ParseKeys } from 'i18next'
import { useTranslation } from 'react-i18next'

import {
  runQueryOptions,
  runRefusalOf,
  type AiStopReason,
  type Run,
  type RunStep,
  type StepTool,
} from '../api/usage'
import { toolNameKey } from '../agent/toolNames'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { Dot } from '../components/Dot'
import { ExpandHint } from '../components/ExpandHint'
import { PAGE_TITLE, TEXT_LINK } from '../components/controls'
import { QueueLoading } from '../components/QueueLoading'
import { RequestFailed } from '../components/RequestFailed'
import { SectionHeading } from '../components/SectionHeading'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { TechnicalDetails } from '../components/TechnicalDetails'
import { Timestamp } from '../components/Timestamp'
import { OUTCOME_TEXT, STOP_TEXT } from '../usage/labels'
import { duration, maybeTokens, percent, tokens, usd } from '../usage/numbers'

/**
 * 一輪的步驟（M5 票 21，`.scratch/m5/usage-and-run-shape.md`〈步驟頁〉）：側面板每一則回覆連過來。
 * 照時間列出每一次模型呼叫與它叫的工具，各自的 token、耗時、結果，最後是停止原因。被防護中止的
 * 那一輪也一樣有數字（每次模型呼叫之後當場記帳，brief §20.24）。還在跑的每 2 秒重問。
 */
export function RunPage({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const run = useQuery(runQueryOptions(runId))

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <h1 className={PAGE_TITLE}>{t('usage.run.title')}</h1>
      <div className="mt-6 grid gap-8">
        {run.isPending ? <QueueLoading /> : null}
        {run.isError ? (
          runRefusalOf(run.error)?.reason === 'run_missing' ? (
            <p className="text-sm text-ink">{t('usage.run.missing')}</p>
          ) : (
            <RequestFailed error={run.error} lead={t('usage.run.failedLead')} />
          )
        ) : null}
        {run.data ? <RunBody run={run.data} /> : null}
      </div>
    </div>
  )
}

/** 停止原因 → 色塊。防護停下是「需要你決定下一步」（`assigned`），出錯是擋住了（`blocked`）。 */
const STOP_CHIP: Record<AiStopReason, { signal: Signal; key: ParseKeys }> = {
  completed: { signal: 'neutral', key: 'usage.run.chip.completed' },
  request_limit: { signal: 'assigned', key: 'usage.run.chip.stopped' },
  token_limit: { signal: 'assigned', key: 'usage.run.chip.stopped' },
  repeated_call: { signal: 'assigned', key: 'usage.run.chip.stopped' },
  ping_pong: { signal: 'assigned', key: 'usage.run.chip.stopped' },
  no_progress: { signal: 'assigned', key: 'usage.run.chip.stopped' },
  circuit_open: { signal: 'blocked', key: 'usage.run.chip.failed' },
  error: { signal: 'blocked', key: 'usage.run.chip.failed' },
  cancelled: { signal: 'neutral', key: 'usage.run.chip.cancelled' },
}

function RunBody({ run }: { run: Run }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const none = t('usage.none')
  const chip = run.stop_reason
    ? STOP_CHIP[run.stop_reason]
    : { signal: 'working' as const, key: 'usage.run.chip.running' as const }
  const spent =
    run.ended_at === null
      ? none
      : duration(new Date(run.ended_at).getTime() - new Date(run.started_at).getTime(), language)
  const hitRate =
    run.cache_read_tokens === null || run.input_tokens === 0
      ? null
      : run.cache_read_tokens / run.input_tokens

  return (
    <>
      <div className="-mt-6 grid gap-3">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-dim">
          <Timestamp at={run.started_at} past />
          <Dot />
          <span>{t('usage.run.who', { name: run.user_name })}</span>
          <Dot />
          <span className="value text-xs wrap-anywhere">{`${run.provider} · ${run.model}`}</span>
        </p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2" aria-live="polite">
          <span className={`label px-2 py-1.5 ${SIGNAL_FILL[chip.signal]}`}>{t(chip.key)}</span>
          <span className="text-sm text-ink">{t(STOP_TEXT[run.stop_reason ?? 'running'])}</span>
          <TechnicalDetails lines={[run.error]} inline />
        </div>
        {run.continues ? (
          <p className="text-sm text-ink">
            {t('usage.run.continues')}{' '}
            <Link to="/agent/runs/$runId" params={{ runId: run.continues }} className={TEXT_LINK}>
              {t('usage.run.continuesLink')}
            </Link>
          </p>
        ) : null}
      </div>
      <Cutaway title={t('usage.run.summary.title')} level={2}>
        <CutawayRow term={t('usage.run.summary.calls')} value={tokens(run.requests, language)} />
        <CutawayRow term={t('usage.run.summary.tools')} value={tokens(run.tool_calls, language)} />
        <CutawayRow
          term={t('usage.run.summary.input')}
          value={tokens(run.input_tokens, language)}
        />
        <CutawayRow
          term={t('usage.run.summary.cacheRead')}
          value={maybeTokens(run.cache_read_tokens, language, none)}
        />
        <CutawayRow
          term={t('usage.run.summary.cacheWrite')}
          value={maybeTokens(run.cache_write_tokens, language, none)}
        />
        <CutawayRow
          term={t('usage.run.summary.output')}
          value={tokens(run.output_tokens, language)}
        />
        <CutawayRow term={t('usage.run.summary.hitRate')} value={percent(hitRate, none)} />
        <CutawayRow
          term={t('usage.run.summary.cost')}
          value={run.cost_usd === null ? t('usage.unknown') : usd(run.cost_usd, language)}
        />
        <CutawayRow
          term={t('usage.run.summary.searches')}
          value={t('usage.run.summary.searchesValue', {
            server: run.web_searches,
            tavily: run.tavily_searches,
          })}
        />
        <CutawayRow term={t('usage.run.summary.duration')} value={spent} />
      </Cutaway>
      <section aria-labelledby="run-steps" className="grid min-w-0 gap-3">
        <SectionHeading id="run-steps" label={t('usage.run.steps')} />
        {run.steps.length === 0 ? (
          <p className="text-sm text-ink">{t('usage.run.empty')}</p>
        ) : (
          <ol className="grid gap-3">
            {run.steps.map((step) => (
              <Step key={step.step} step={step} />
            ))}
          </ol>
        )}
      </section>
    </>
  )
}

function Step({ step }: { step: RunStep }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const none = t('usage.none')
  const call = step.call
  const failed = call !== null && call.error !== ''

  return (
    <li
      className={`grid min-w-0 gap-2 border-2 bg-well px-4 py-3 ${failed ? 'border-rule-strong' : 'border-rule'}`}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="label text-ink">
          {call === null
            ? t('usage.run.callMissing', { step: step.step })
            : t('usage.run.call', { step: step.step })}
        </h3>
        {call ? (
          <>
            <span className="value min-w-0 text-xs wrap-anywhere text-ink">{call.model}</span>
            <span className="value ms-auto text-xs text-ink-dim tabular-nums">
              {duration(call.duration_ms, language)}
            </span>
          </>
        ) : null}
      </div>
      {call ? (
        <p className="value flex flex-wrap gap-x-2 gap-y-1 text-xs text-ink-dim tabular-nums">
          {[
            `${t('usage.run.summary.input')} ${tokens(call.input_tokens, language)}`,
            `${t('usage.run.summary.cacheRead')} ${maybeTokens(call.cache_read_tokens, language, none)}`,
            `${t('usage.run.summary.cacheWrite')} ${maybeTokens(call.cache_write_tokens, language, none)}`,
            `${t('usage.run.summary.output')} ${tokens(call.output_tokens, language)}`,
            call.cost_usd === null ? t('usage.unknown') : usd(call.cost_usd, language),
            ...(call.web_searches > 0
              ? [t('usage.run.searches', { value: call.web_searches })]
              : []),
            ...(call.finish_reason ? [t('usage.run.finish', { reason: call.finish_reason })] : []),
          ].map((text, index) => (
            <span key={index} className="inline-flex gap-x-2">
              {index > 0 ? <Dot /> : null}
              {text}
            </span>
          ))}
        </p>
      ) : null}
      {failed ? (
        <div className="grid gap-1">
          <p className="text-sm text-blocked-ink">{t('usage.run.callError')}</p>
          <TechnicalDetails lines={[call.error]} />
        </div>
      ) : null}
      {step.tools.length > 0 ? (
        <ul className="ms-4 grid gap-2">
          {step.tools.map((tool, index) => (
            <Tool key={index} tool={tool} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

function pretty(json: string): string {
  try {
    return JSON.stringify(JSON.parse(json), null, 2)
  } catch {
    // 截在 2000 字的參數不是完整的 JSON：照原文。
    return json
  }
}

function Tool({ tool }: { tool: StepTool }) {
  const { t, i18n } = useTranslation()
  const key = toolNameKey(tool.command)
  const stopped = tool.outcome !== 'ok' && tool.outcome !== 'warned'

  return (
    <li
      className={`grid min-w-0 gap-1 border-2 bg-hull px-3 py-2 ${stopped ? 'border-rule-strong' : 'border-rule'}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="label text-ink-dim">{t('usage.run.toolLabel')}</span>
        {key ? (
          <span className="min-w-0 text-sm text-ink">{t(key)}</span>
        ) : (
          <span className="value min-w-0 text-xs wrap-anywhere text-ink">{tool.command}</span>
        )}
        <span className="label text-ink">{t(OUTCOME_TEXT[tool.outcome])}</span>
        {tool.truncated ? (
          <span className="label text-ink-dim">{t('usage.run.truncated')}</span>
        ) : null}
        <span className="value ms-auto text-xs text-ink-dim tabular-nums">
          {duration(tool.duration_ms, i18n.language)}
        </span>
      </div>
      {tool.detail ? (
        <p className="value text-xs whitespace-pre-wrap wrap-anywhere text-ink">{tool.detail}</p>
      ) : null}
      <details className="group min-w-0">
        <summary className="flex min-h-6 cursor-pointer items-center gap-2 [&::-webkit-details-marker]:hidden">
          <span className="label text-ink-dim">{t('usage.run.args')}</span>
          <ExpandHint />
        </summary>
        <pre className="value mt-1 text-xs whitespace-pre-wrap wrap-anywhere text-ink">
          {pretty(tool.args_json)}
        </pre>
      </details>
    </li>
  )
}

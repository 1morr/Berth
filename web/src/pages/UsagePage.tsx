import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { agentStatusQueryOptions } from '../api/agent'
import {
  saveSpendAlert,
  usageQueryOptions,
  type AiStopReason,
  type DayUsage,
  type Usage,
} from '../api/usage'
import { Cutaway, CutawayRow } from '../components/Cutaway'
import { Dot } from '../components/Dot'
import { Field, GhostButton, Notice, TEXT_LINK } from '../components/controls'
import { QueueLoading } from '../components/QueueLoading'
import { RequestFailed } from '../components/RequestFailed'
import { Timestamp } from '../components/Timestamp'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { alertText } from '../usage/alerts'
import { STOP_TEXT } from '../usage/labels'
import { percent, tally, tokens, usd } from '../usage/numbers'

/**
 * AI 用量頁（M5 票 21，`.scratch/m5/usage-and-run-shape.md`）：管理員看「用了多少、哪一天特別燒、
 * 燒在哪一輪」。只有數字表，不畫圖（DESIGN.md 拒絕的類別預設：折線圖儀表板）。
 *
 * **不知道的不當 0**：接口沒報的格子寫「—」，部分算不出來的費用接「+未知」，說明在表下。
 * **花費只提醒、不停用**：提醒是一句話，沒有任何東西照它擋下 AI。
 */
export function UsagePage() {
  const { t } = useTranslation()
  const usage = useQuery(usageQueryOptions)

  return (
    <SettingsFrame title={t('usage.title')} lede={t('usage.lede')}>
      {usage.isPending ? <QueueLoading /> : null}
      {usage.isError ? <RequestFailed error={usage.error} lead={t('usage.failedLead')} /> : null}
      {usage.data ? <UsageBody usage={usage.data} /> : null}
    </SettingsFrame>
  )
}

function UsageBody({ usage }: { usage: Usage }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const today = usage.days[0]

  return (
    <>
      {usage.alerts.length > 0 ? (
        <div className="grid gap-2">
          {usage.alerts.map((alert) => (
            <Notice key={alert.kind} signal="assigned" label={t('usage.alerts.label')}>
              {alertText(t, alert, language, 'page')}
            </Notice>
          ))}
        </div>
      ) : null}
      <Cutaway title={t('usage.summary.title')} level={2}>
        <CutawayRow term={t('usage.summary.today')} value={<Cost day={today} />} />
        <CutawayRow term={t('usage.summary.total')} value={<Cost day={usage.totals} />} />
        <CutawayRow term={t('usage.summary.runs')} value={tokens(usage.runs_count, language)} />
        <CutawayRow term={t('usage.summary.calls')} value={tokens(usage.totals.calls, language)} />
        <CutawayRow
          term={t('usage.summary.hitRate')}
          value={percent(usage.totals.hit_rate, t('usage.none'))}
        />
      </Cutaway>
      <AlertForm saved={usage.daily_alert_usd} />
      <Days days={usage.days} />
      <Guards usage={usage} />
      <Runs usage={usage} />
      <Prices usage={usage} />
    </>
  )
}

/** 一天（或合計）的估計費用：部分算不出來接「+未知」，全部算不出來是「未知」。 */
function Cost({ day }: { day: DayUsage }) {
  const { t, i18n } = useTranslation()
  return (
    <>
      {tally(day.cost, (known) => usd(known, i18n.language), {
        none: t('usage.unknown'),
        partial: (known) => t('usage.partial', { known }),
      })}
    </>
  )
}

function AlertForm({ saved }: { saved: number | null }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [value, setValue] = useState(saved === null ? '' : String(saved))
  const [invalid, setInvalid] = useState(false)
  const save = useMutation({
    mutationFn: saveSpendAlert,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: usageQueryOptions.queryKey }),
        queryClient.invalidateQueries({ queryKey: agentStatusQueryOptions.queryKey }),
      ])
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const text = value.trim()
    const amount = text === '' ? null : Number(text)
    if (amount !== null && (!Number.isFinite(amount) || amount < 0)) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    save.mutate(amount)
  }

  const done = save.isSuccess ? save.data.daily_usd : undefined
  return (
    <SettingsSection id="usage-alert" title={t('usage.alert.title')} lede={t('usage.alert.lede')}>
      {/* `noValidate`：負數由這裡說成一句話，不交給瀏覽器各自的泡泡。 */}
      <form noValidate onSubmit={onSubmit} className="grid max-w-sm gap-3">
        <Field
          label={t('usage.alert.field')}
          hint={t('usage.alert.hint')}
          error={invalid ? t('usage.alert.invalid') : undefined}
          type="number"
          inputMode="decimal"
          min={0}
          step="any"
          value={value}
          onChange={(event) => {
            setValue(event.target.value)
            save.reset()
          }}
        />
        <div className="flex">
          <GhostButton type="submit" busy={save.isPending}>
            {t('usage.alert.save')}
          </GhostButton>
        </div>
        <div aria-live="polite" className="empty:hidden">
          {done === null ? <p className="text-sm text-ink">{t('usage.alert.cleared')}</p> : null}
          {typeof done === 'number' ? (
            <p className="text-sm text-ink">
              {t('usage.alert.saved', { value: usd(done, i18n.language) })}
            </p>
          ) : null}
          {save.isError ? (
            <RequestFailed error={save.error} lead={t('usage.alert.failedLead')} />
          ) : null}
        </div>
      </form>
    </SettingsSection>
  )
}

/**
 * 逐日表。**一份 DOM 兩種版面**（DESIGN.md〈窄版的收法〉）：窄的時候只畫日期與費用兩欄，其餘收成
 * 日期底下一行、每一格自己說出它是什麼。看的是表格自己的寬（container query）而不是視窗：側面板
 * 打開時頁面變窄，視窗卻沒變。
 */
function Days({ days }: { days: DayUsage[] }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const none = t('usage.none')
  const wide = 'hidden @2xl:table-cell'
  const head = 'label px-3 py-2 text-ink-dim'

  return (
    <SettingsSection id="usage-days" title={t('usage.days.title')}>
      <div className="@container grid gap-3">
        <table className="w-full border-2 border-rule bg-well text-left">
          <caption className="sr-only">{t('usage.days.caption')}</caption>
          <thead className="border-b-2 border-rule bg-deck">
            <tr>
              <th scope="col" className={head}>
                {t('usage.days.day')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.newInput')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.cacheRead')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.cacheWrite')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.output')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.hitRate')}
              </th>
              <th scope="col" className={`${head} text-right`}>
                {t('usage.days.cost')}
              </th>
              <th scope="col" className={`${head} ${wide} text-right`}>
                {t('usage.days.searches')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {days.map((day, index) => {
              const cells = {
                newInput: tokens(day.new_input, language),
                cacheRead: tally(day.cache_read, (n) => tokens(n, language), {
                  none,
                  partial: (known) => t('usage.partial', { known }),
                }),
                cacheWrite: tally(day.cache_write, (n) => tokens(n, language), {
                  none,
                  partial: (known) => t('usage.partial', { known }),
                }),
                output: tokens(day.output_tokens, language),
                hitRate: percent(day.hit_rate, none),
                searches: searchesText(t, day),
              }
              const cell = `${wide} value px-3 py-2 text-right align-baseline text-xs text-ink tabular-nums`
              return (
                <tr key={day.day}>
                  <th
                    scope="row"
                    className="min-w-0 px-3 py-2 text-left align-baseline font-normal"
                  >
                    <span className="value text-sm text-ink tabular-nums">
                      {index === 0 ? `${day.day} · ${t('usage.days.today')}` : day.day}
                    </span>
                    <span className="value mt-1 flex flex-wrap gap-x-2 text-xs text-ink-dim @2xl:hidden">
                      {(
                        [
                          ['newInput', cells.newInput],
                          ['cacheRead', cells.cacheRead],
                          ['cacheWrite', cells.cacheWrite],
                          ['output', cells.output],
                          ['hitRate', cells.hitRate],
                          ['searches', cells.searches],
                        ] as const
                      ).map(([key, text], position) => (
                        <span key={key} className="inline-flex gap-x-2">
                          {position > 0 ? <Dot /> : null}
                          {t('usage.days.labeled', { label: t(`usage.days.${key}`), value: text })}
                        </span>
                      ))}
                    </span>
                  </th>
                  <td className={cell}>{cells.newInput}</td>
                  <td className={cell}>{cells.cacheRead}</td>
                  <td className={cell}>{cells.cacheWrite}</td>
                  <td className={cell}>{cells.output}</td>
                  <td className={cell}>{cells.hitRate}</td>
                  <td className="value px-3 py-2 text-right align-baseline text-sm text-ink tabular-nums">
                    <Cost day={day} />
                  </td>
                  <td className={cell}>{cells.searches}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="grid max-w-prose gap-1 text-xs text-ink-dim">
          <p>{t('usage.days.notes.unknown')}</p>
          <p>{t('usage.days.notes.newInput')}</p>
        </div>
      </div>
    </SettingsSection>
  )
}

function searchesText(t: TFunction, day: DayUsage): string {
  const server = String(day.web_searches)
  return day.tavily_searches > 0
    ? `${server} · ${t('usage.days.tavily', { value: day.tavily_searches })}`
    : server
}

function Guards({ usage }: { usage: Usage }) {
  const { t } = useTranslation()
  const count = (value: number) => t('usage.guards.count', { count: value })
  const stops = Object.entries(usage.guards.stops) as [AiStopReason, number][]

  return (
    <SettingsSection
      id="usage-guards"
      title={t('usage.guards.title')}
      lede={t('usage.guards.lede')}
    >
      <div className="grid gap-4">
        <Cutaway title={t('usage.guards.stopsTitle')}>
          {stops.map(([reason, value]) => (
            <CutawayRow
              key={reason}
              term={t(STOP_TEXT[reason])}
              value={count(value)}
              muted={value === 0}
            />
          ))}
        </Cutaway>
        <Cutaway title={t('usage.guards.toolsTitle')}>
          {(['blocked', 'refused', 'failed', 'truncated'] as const).map((key) => (
            <CutawayRow
              key={key}
              term={t(`usage.guards.tools.${key}`)}
              value={count(usage.guards[key])}
              muted={usage.guards[key] === 0}
            />
          ))}
        </Cutaway>
      </div>
    </SettingsSection>
  )
}

function Runs({ usage }: { usage: Usage }) {
  const { t, i18n } = useTranslation()
  const language = i18n.language
  const wide = 'hidden @2xl:table-cell'
  const head = 'label px-3 py-2 text-ink-dim'

  return (
    <SettingsSection id="usage-runs" title={t('usage.runs.title')}>
      {usage.runs.length === 0 ? (
        <p className="text-sm text-ink">{t('usage.runs.empty')}</p>
      ) : (
        <div className="@container">
          <table className="w-full border-2 border-rule bg-well text-left">
            <caption className="sr-only">{t('usage.runs.caption')}</caption>
            <thead className="border-b-2 border-rule bg-deck">
              <tr>
                <th scope="col" className={head}>
                  {t('usage.runs.time')}
                </th>
                <th scope="col" className={`${head} ${wide}`}>
                  {t('usage.runs.who')}
                </th>
                <th scope="col" className={`${head} ${wide}`}>
                  {t('usage.runs.steps')}
                </th>
                <th scope="col" className={`${head} ${wide} text-right`}>
                  {t('usage.runs.tokens')}
                </th>
                <th scope="col" className={`${head} text-right`}>
                  {t('usage.runs.cost')}
                </th>
                <th scope="col" className={`${head} ${wide}`}>
                  {t('usage.runs.stop')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {usage.runs.map((run) => {
                const steps = t('usage.runs.stepsValue', {
                  requests: run.requests,
                  tools: run.tool_calls,
                })
                const tokenText = t('usage.runs.tokensValue', {
                  input: tokens(run.input_tokens, language),
                  output: tokens(run.output_tokens, language),
                })
                const stop = t(STOP_TEXT[run.stop_reason ?? 'running'])
                const cell = `${wide} px-3 py-2 align-baseline text-xs text-ink`
                return (
                  <tr key={run.id}>
                    <th
                      scope="row"
                      className="min-w-0 px-3 py-2 text-left align-baseline font-normal"
                    >
                      <Link
                        to="/agent/runs/$runId"
                        params={{ runId: run.id }}
                        className={`${TEXT_LINK} text-sm`}
                        aria-label={`${t('usage.runs.open')}: ${run.started_at}`}
                      >
                        <Timestamp at={run.started_at} past />
                      </Link>
                      <span className="mt-1 flex flex-wrap gap-x-2 text-xs text-ink-dim @2xl:hidden">
                        <span>{run.user_name}</span>
                        <Dot />
                        <span>{steps}</span>
                        <Dot />
                        <span className="value">{tokenText}</span>
                        <Dot />
                        <span>{stop}</span>
                      </span>
                    </th>
                    <td className={cell}>{run.user_name}</td>
                    <td className={cell}>{steps}</td>
                    <td className={`${cell} value text-right tabular-nums`}>{tokenText}</td>
                    <td className="value px-3 py-2 text-right align-baseline text-sm text-ink tabular-nums">
                      {run.cost_usd === null ? t('usage.unknown') : usd(run.cost_usd, language)}
                    </td>
                    <td className={cell}>{stop}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </SettingsSection>
  )
}

function Prices({ usage }: { usage: Usage }) {
  const { t } = useTranslation()
  return (
    <SettingsSection id="usage-prices" title={t('usage.prices.title')}>
      <ul className="grid max-w-prose gap-2 text-sm text-ink-dim">
        {usage.prices.map(({ model, price }) => (
          <li key={model} className="wrap-anywhere">
            {price === null
              ? t('usage.prices.unknown', { model })
              : t('usage.prices.model', {
                  model,
                  input: price.input,
                  output: price.output,
                  cacheRead: price.cache_read,
                  cacheWrite: price.cache_write,
                  verified: price.verified,
                })}
          </li>
        ))}
        <li>{t('usage.prices.byName')}</li>
        <li>{t('usage.prices.webSearch')}</li>
        <li>{t('usage.prices.tavily')}</li>
      </ul>
    </SettingsSection>
  )
}

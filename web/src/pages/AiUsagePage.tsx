import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearch } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import {
  aiUsageQueryOptions,
  DEFAULT_USAGE_PERIOD,
  USAGE_PERIODS,
  type AiCallOrigin,
  type AiFailure,
  type AiUsage,
  type UsagePeriod,
} from '../api/ai'
import { FILTER, GHOST_LINK, Notice } from '../components/controls'
import { ExpandHint } from '../components/ExpandHint'
import { FilterBar } from '../components/FilterBar'
import { RequestFailed } from '../components/RequestFailed'
import { SettingsFrame, SettingsSection } from '../settings/SettingsFrame'
import { UsageChart } from '../settings/UsageChart'
import { useUsageFormat } from '../settings/usageFormat'
import { HEAD_CELL, USAGE_TABLE, UsageTable } from '../settings/UsageTable'

/** 出處的名字。少一種就編譯不過：M6 加了 AI 任務，這裡跟著補一格。 */
const ORIGIN_TEXT = {
  test: 'settings.usagePage.origin.test',
  conversation: 'settings.usagePage.origin.conversation',
} as const satisfies Record<AiCallOrigin, string>

const FAILURE_TEXT = {
  rate_limited: 'settings.usagePage.failure.rate_limited',
  quota_exhausted: 'settings.usagePage.failure.quota_exhausted',
  provider_down: 'settings.usagePage.failure.provider_down',
  auth_failed: 'settings.usagePage.failure.auth_failed',
  model_not_found: 'settings.usagePage.failure.model_not_found',
  unreachable: 'settings.usagePage.failure.unreachable',
  rejected: 'settings.usagePage.failure.rejected',
} as const satisfies Record<AiFailure, string>

/**
 * 設定 → 用量（M5 票 13，`.scratch/m5/usage-page-shape.md`）：今天往前 7 / 30 / 90 天的 tokens 與快取命中率，
 * 依日期、出處、格式與模型、人，與沒成的次數。只有管理員（看得到每個人的用量）。不設預算，只是看的。
 *
 * 形狀照 Anthropic Console 與 OpenAI 的用量頁：依日直條、依 token 種類分段、可分組的表、幾個固定的期間；
 * 不畫金額（Berth 不知道第三方的價格）。
 */
export function AiUsagePage() {
  const { t } = useTranslation()
  const { days: requested } = useSearch({ from: '/settings/usage' })
  const days = requested ?? DEFAULT_USAGE_PERIOD
  // 換期間時手上留著上一段：總量與圖照畫，不閃成讀取中。
  const usage = useQuery({ ...aiUsageQueryOptions(days), placeholderData: keepPreviousData })

  return (
    <SettingsFrame title={t('settings.usagePage.title')} lede={t('settings.usagePage.lede')}>
      {usage.isPending ? (
        <Loading />
      ) : !usage.data ? (
        <RequestFailed error={usage.error} lead={t('settings.usagePage.readFailed')} />
      ) : !usage.data.has_any ? (
        <FirstCall />
      ) : (
        <Report usage={usage.data} days={days} />
      )}
    </SettingsFrame>
  )
}

/** 讀取中：總量列與圖的位置是不動的色條，與真的一樣高（DESIGN.md 的讀取中佔位）。 */
function Loading() {
  return (
    <div aria-hidden="true" className="grid gap-6">
      <div className="h-[8.5rem] bg-deck sm:h-[4.25rem]" />
      <div className="h-[13.5rem] bg-deck" />
    </div>
  )
}

/** 有史以來一筆都沒有：說怎麼開始，不畫空圖、不畫一排 0。 */
function FirstCall() {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3">
      <Notice signal="neutral" label={t('settings.usagePage.empty.label')}>
        {t('settings.usagePage.empty.body')}
      </Notice>
      <Link to="/settings/ai" className={GHOST_LINK}>
        {t('settings.usagePage.empty.go')}
      </Link>
    </div>
  )
}

function Report({ usage, days }: { usage: AiUsage; days: UsagePeriod }) {
  const { t } = useTranslation()
  const quiet = usage.totals.calls === 0
  const longest = USAGE_PERIODS[USAGE_PERIODS.length - 1]

  return (
    <>
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Periods days={days} />
          <p className="value text-xs text-ink-dim">
            {t('settings.usagePage.range', { since: usage.since, until: usage.until })}
          </p>
        </div>
        <Totals usage={usage} />
        {quiet && (
          <p className="text-sm text-ink">
            {t('settings.usagePage.emptyPeriod')}{' '}
            {longest !== undefined && days !== longest && (
              <Link to="/settings/usage" search={{ days: longest }} className="underline">
                {t('settings.usagePage.longer', { count: longest })}
              </Link>
            )}
          </p>
        )}
      </div>

      <SettingsSection
        id="usage-by-day"
        title={t('settings.usagePage.chart.title')}
        lede={t('settings.usagePage.chart.lede')}
      >
        <div className="grid gap-3">
          <UsageChart days={usage.days} />
          {!quiet && <Daily usage={usage} />}
        </div>
      </SettingsSection>

      {!quiet && <Breakdowns usage={usage} />}
    </>
  )
}

/** 7 / 30 / 90 天。在網址上（預設的 30 不寫），選著的那一個不是連結（`FilterBar`）。 */
function Periods({ days }: { days: UsagePeriod }) {
  const { t } = useTranslation()

  return (
    <FilterBar
      label={t('settings.usagePage.periods')}
      options={USAGE_PERIODS.map((option) => ({
        value: String(option),
        label: t('settings.usagePage.period', { count: option }),
      }))}
      current={String(days)}
      renderOption={(option, label) => {
        const period = Number(option) as UsagePeriod
        return (
          <Link
            to="/settings/usage"
            search={period === DEFAULT_USAGE_PERIOD ? {} : { days: period }}
            className={FILTER}
          >
            {label}
          </Link>
        )
      }}
    />
  )
}

/**
 * 期間的總量：五格，與泊位板同一種 `gap-px` 的格子，不上信號色（用量不是狀態）。命中率那一格底下說
 * 有幾次沒回報快取、或為什麼算不出來。
 */
function Totals({ usage }: { usage: AiUsage }) {
  const { t } = useTranslation()
  const format = useUsageFormat()
  const totals = usage.totals
  const cells = [
    ['calls', format.count(totals.calls)],
    ['input', format.count(totals.input_tokens)],
    ['output', format.count(totals.output_tokens)],
    ['hitRate', format.rate(totals.hit_rate)],
    ['failed', format.count(totals.failed)],
  ] as const

  return (
    <section aria-label={t('settings.usagePage.totals.label')}>
      <dl className="grid grid-cols-2 gap-px border-2 border-rule bg-rule sm:grid-cols-5">
        {cells.map(([key, value]) => (
          <div key={key} className="min-w-0 bg-well px-3 py-2.5 last:col-span-2 sm:last:col-span-1">
            <dt className="label text-ink-dim">{t(`settings.usagePage.totals.${key}`)}</dt>
            <dd className="value mt-1 text-sm text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      {totals.calls > 0 && totals.hit_rate === null && (
        <p className="mt-2 text-xs text-ink-dim">{t('settings.usagePage.totals.noRate')}</p>
      )}
      {totals.cache_unreported > 0 && (
        <p className="mt-2 text-xs text-ink-dim">
          {t('settings.usagePage.unreported', { count: totals.cache_unreported })}
        </p>
      )}
    </section>
  )
}

/** 逐日表收在 `<details>` 裡：只列有呼叫的日子，新的在上。這張表也是圖的無障礙等價物。 */
function Daily({ usage }: { usage: AiUsage }) {
  const { t } = useTranslation()
  const active = usage.days.filter((day) => day.tally.calls > 0).reverse()

  return (
    <details className="group border-2 border-rule">
      <summary className="flex cursor-pointer items-baseline gap-3 px-3 py-2 marker:content-none">
        <span id="usage-daily" className="label text-ink">
          {t('settings.usagePage.daily')}
        </span>
        <ExpandHint className="ml-auto" />
      </summary>
      <div className="border-t-2 border-rule bg-hull p-3">
        <UsageTable
          labelledBy="usage-daily"
          first={t('settings.usagePage.column.date')}
          lines={active.map((day) => ({ key: day.date, label: day.date, tally: day.tally }))}
        />
      </div>
    </details>
  )
}

function Breakdowns({ usage }: { usage: AiUsage }) {
  const { t } = useTranslation()
  const format = useUsageFormat()

  return (
    <>
      <SettingsSection id="usage-by-origin" title={t('settings.usagePage.byOrigin')}>
        <UsageTable
          labelledBy="usage-by-origin"
          first={t('settings.usagePage.column.origin')}
          lines={usage.by_origin.map((line) => ({
            key: line.origin,
            label: t(ORIGIN_TEXT[line.origin]),
            prose: true,
            tally: line.tally,
          }))}
        />
      </SettingsSection>

      <SettingsSection
        id="usage-by-model"
        title={t('settings.usagePage.byModel.title')}
        lede={t('settings.usagePage.byModel.lede')}
      >
        <UsageTable
          labelledBy="usage-by-model"
          first={t('settings.usagePage.column.model')}
          lines={usage.by_model.map((line) => ({
            key: `${line.format} ${line.host} ${line.model}`,
            label: line.model,
            sub: `${t(`settings.usagePage.format.${line.format}`)} · ${line.host}`,
            tally: line.tally,
          }))}
        />
      </SettingsSection>

      <SettingsSection id="usage-by-user" title={t('settings.usagePage.byUser.title')}>
        <UsageTable
          labelledBy="usage-by-user"
          first={t('settings.usagePage.column.person')}
          lines={usage.by_user.map((line) => ({
            key: String(line.user_id),
            label: line.name ?? t('settings.usagePage.byUser.nobody'),
            prose: line.name === null,
            tally: line.tally,
          }))}
        />
      </SettingsSection>

      <SettingsSection
        id="usage-failures"
        title={t('settings.usagePage.failures.title')}
        lede={t('settings.usagePage.failures.lede')}
      >
        {usage.failures.length === 0 ? (
          <p className="text-sm text-ink">{t('settings.usagePage.failures.none')}</p>
        ) : (
          <table aria-labelledby="usage-failures" className={USAGE_TABLE}>
            <thead>
              <tr>
                <th scope="col" className={HEAD_CELL}>
                  {t('settings.usagePage.failures.column')}
                </th>
                <th scope="col" className={`${HEAD_CELL} text-right`}>
                  {t('settings.usagePage.failures.count')}
                </th>
              </tr>
            </thead>
            <tbody>
              {usage.failures.map((line) => (
                <tr key={line.failure} className="border-t-2 border-rule">
                  <th scope="row" className="px-3 py-2 text-sm font-normal text-ink">
                    {t(FAILURE_TEXT[line.failure])}
                  </th>
                  <td className="value px-3 py-2 text-right text-sm">{format.count(line.calls)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SettingsSection>
    </>
  )
}

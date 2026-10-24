import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { AiUsage } from '../api/ai'
import { Dot } from '../components/Dot'
import { SEGMENT_FILL, SEGMENTS, segmentsOf, useUsageFormat } from './usageFormat'

type Day = AiUsage['days'][number]

/**
 * 依日的堆疊直條（M5 票 13，`.scratch/m5/usage-page-shape.md`）。每天一根，沒有呼叫的日子只剩基線。
 *
 * - **沒有浮動 tooltip**：這套系統沒有 z 軸（DESIGN.md Elevation）。圖上方一行讀數，平常說最後一天，
 *   指標滑過或按到一根就換成那一天——值貼在它那一行，不疊在圖上。
 * - **圖本身 `aria-hidden`**：九十根各自可聚焦是九十個 Tab 停留點。鍵盤與螢幕閱讀器的等價物是下面的
 *   逐日表（dataviz：一定要有表格檢視）；讀數那一行是一般文字，照樣讀得到。
 * - 直角、柱與柱 `gap-px`、段與段之間 1px 的底色縫（DESIGN.md 零圓角與 1px 縫，壓過 dataviz 的 4px 圓頭與 2px 縫）。
 */
export function UsageChart({ days }: { days: AiUsage['days'] }) {
  const { t } = useTranslation()
  const format = useUsageFormat()
  const [pointed, setPointed] = useState<number | null>(null)
  const peak = Math.max(0, ...days.map((day) => total(day)))
  const shown = days[pointed ?? days.length - 1]

  return (
    <figure className="grid gap-3">
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="sr-only">{t('settings.usagePage.chart.legend')}</span>
        {SEGMENTS.map((segment) => (
          <span key={segment} className="flex items-center gap-1.5 text-xs text-ink">
            <span aria-hidden="true" className={`size-3 ${SEGMENT_FILL[segment]}`} />
            {t(`settings.usagePage.segment.${segment}`)}
          </span>
        ))}
      </figcaption>

      {shown && <Readout day={shown} />}

      <div className="border-2 border-rule bg-well px-3 pt-3 pb-2">
        <p className="value text-xs text-ink-dim">
          {t('settings.usagePage.chart.peak', { value: format.count(peak) })}
        </p>
        <div
          aria-hidden="true"
          className="mt-1 flex h-40 items-stretch gap-px border-b-2 border-rule-strong"
          onPointerLeave={() => setPointed(null)}
        >
          {days.map((day, index) => (
            <div
              key={day.date}
              data-testid="usage-bar"
              data-pointed={pointed === index ? 'true' : undefined}
              className="flex min-w-0 flex-1 flex-col-reverse gap-px data-[pointed=true]:bg-deck"
              onPointerEnter={() => setPointed(index)}
              onPointerDown={() => setPointed(index)}
            >
              {SEGMENTS.map((segment) => {
                const value = segmentsOf(day.tally)[segment]
                if (value === 0 || peak === 0) return null
                return (
                  <div
                    key={segment}
                    className={`min-h-px ${SEGMENT_FILL[segment]}`}
                    style={{ height: `${(value / peak) * 100}%` }}
                  />
                )
              })}
            </div>
          ))}
        </div>
        <div className="value mt-1 flex justify-between gap-3 text-xs text-ink-dim">
          <span>{days[0]?.date}</span>
          <span>{days.at(-1)?.date}</span>
        </div>
      </div>
    </figure>
  )
}

function total(day: Day): number {
  const segments = segmentsOf(day.tally)
  return segments.cacheRead + segments.otherInput + segments.output
}

/** 一天的讀數：日期 · 三段 · 呼叫數 · 命中率。 */
function Readout({ day }: { day: Day }) {
  const { t } = useTranslation()
  const format = useUsageFormat()
  const segments = segmentsOf(day.tally)

  return (
    <p data-testid="usage-readout" className="value flex flex-wrap gap-x-2 text-xs text-ink">
      <span className="font-semibold">{day.date}</span>
      <Dot />
      {day.tally.calls === 0 ? (
        <span>{t('settings.usagePage.chart.noCalls')}</span>
      ) : (
        <>
          {SEGMENTS.map((segment) => (
            <span key={segment} className="flex gap-x-2">
              {t(`settings.usagePage.segment.${segment}`)} {format.count(segments[segment])}
              <Dot />
            </span>
          ))}
          <span>{t('settings.usagePage.chart.calls', { count: day.tally.calls })}</span>
          <Dot />
          <span>
            {t('settings.usagePage.chart.rate', { rate: format.rate(day.tally.hit_rate) })}
          </span>
        </>
      )}
    </p>
  )
}

import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { ScheduleCard } from '../api/schedule'
import { SectionHeading } from '../components/SectionHeading'
import { ScheduleCardRow } from './ScheduleCardRow'
import { monthDay, weekday } from './week'

/** 讀取中每一欄畫幾格空位：一天通常十幾部，三格就說得出「這裡會有一串」。 */
const PLACEHOLDERS = 3

/**
 * 時間表的一天（`.scratch/m5.5/schedule-shape.md`）：標題（`SectionHeading`）是星期、日期與部數，下面是那一天的卡。
 *
 * 今天那一欄頂端一條重橫線加「今天」字塊（形狀加文字，不只靠顏色），`aria-current="date"`。
 * 沒有卡的一天留著、說一句「這天沒有」：七欄要對齊，空的一天也是答案。
 */
export function ScheduleDay({
  day,
  today,
  cards,
  compact = false,
}: {
  day: string
  today: string
  cards: readonly ScheduleCard[]
  /** 七欄並排時星期寫短的（「週二」「Tue」），一次一天時寫全名。 */
  compact?: boolean
}) {
  const { t, i18n } = useTranslation()
  const own = cards.filter((card) => card.air_date === day)
  const isToday = day === today
  // 窄版的一天與桌機的七欄同時在 DOM 裡（只是 CSS 藏起一份），id 不能用日期組。
  const headingId = useId()

  return (
    <section
      aria-labelledby={headingId}
      aria-current={isToday ? 'date' : undefined}
      className={`grid min-w-0 content-start gap-2 border-t-4 pt-2 ${isToday ? 'border-rule-strong' : 'border-transparent'}`}
    >
      <SectionHeading
        id={headingId}
        label={`${weekday(day, i18n.language, compact ? 'short' : 'long')} ${monthDay(day, i18n.language)}`}
        count={{ value: own.length, spoken: t('schedule.count', { count: own.length }) }}
        extra={
          isToday && (
            <span className="label bg-deck px-1.5 py-0.5 text-ink">{t('schedule.today')}</span>
          )
        }
      />
      {own.length === 0 ? (
        <p className="text-sm text-ink-dim">{t('schedule.nothing')}</p>
      ) : (
        <ul className="grid gap-2">
          {own.map((card) => (
            <li key={`${card.media_id}-${String(card.season)}-${String(card.episode)}`}>
              <ScheduleCardRow card={card} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** 讀取中的一欄：幾格與卡片同高的空位，不會動（這個世界沒有骨架屏動畫）。 */
export function ScheduleDayPlaceholder() {
  return (
    <ul aria-hidden="true" className="grid content-start gap-2 border-t-4 border-transparent pt-2">
      <li className="h-5" />
      {Array.from({ length: PLACEHOLDERS }, (_, index) => (
        <li key={index} className="h-[5.75rem] border-2 border-rule bg-well" />
      ))}
    </ul>
  )
}

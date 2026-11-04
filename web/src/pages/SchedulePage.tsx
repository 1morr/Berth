import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { scheduleQueryOptions } from '../api/schedule'
import { FILTER, FILTER_ACTIVE, INLINE_LINK, PAGE_TITLE } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { TmdbAttribution } from '../components/TmdbAttribution'
import { TmdbNotice } from '../components/TmdbNotice'
import { AIRING } from '../nav/sections'
import { SectionTabs } from '../nav/SectionTabs'
import { ScheduleDay, ScheduleDayPlaceholder } from '../schedule/ScheduleDay'
import { monthDay, weekDays, weekday } from '../schedule/week'

/** 七欄並排從這個寬度起（`lg`）；更窄時一次一天。 */
const COLUMNS = 'grid grid-cols-7 gap-3'

/**
 * 時間表 `/schedule`（M5.5 票 09，`.scratch/m5.5/schedule-shape.md`）：這一週 TMDB 上播的動畫，版面照
 * AutoBangumi Calendar（brief §20.3）——週一到週日分欄、今天標出。與它不同的是**預設列全部**：這一頁是拿來
 * 找新番的，訂了的再切「只看已訂閱」。
 *
 * 桌機（`lg` 以上）七欄一起看；窄版一次一天，上面一排七顆日期鍵，預設今天。「今天」照伺服器的時區
 * （後端的 `today`），不照瀏覽器：週界與哪一天的欄是同一個時鐘算的。
 */
export function SchedulePage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const schedule = useQuery(scheduleQueryOptions)
  const [subscribedOnly, setSubscribedOnly] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)

  const week = schedule.data
  const days = week ? weekDays(week.start) : []
  const today = week?.today ?? ''
  const shownDay = picked ?? today
  const cards = (week?.cards ?? []).filter(
    (card) => !subscribedOnly || card.status !== 'unsubscribed',
  )
  const retry = () => void queryClient.invalidateQueries({ queryKey: ['schedule'] })

  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-6 px-6 py-8">
      <SectionTabs section={AIRING} />
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b-2 border-rule-strong pb-2">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 tabIndex={-1} className={PAGE_TITLE}>
            {t('schedule.title')}
          </h1>
          {week && (
            <p className="value text-sm text-ink-dim">
              {t('schedule.range', {
                start: monthDay(week.start, i18n.language),
                end: monthDay(week.end, i18n.language),
              })}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-pressed={subscribedOnly}
          onClick={() => setSubscribedOnly(!subscribedOnly)}
          className={subscribedOnly ? FILTER_ACTIVE : FILTER}
        >
          {t('schedule.subscribedOnly')}
        </button>
      </div>

      {schedule.isPending ? (
        <>
          {/* 第一次打開要讀這一週每一部的詳情（約 160 部），幾秒到十幾秒；之後六小時內是即時的。 */}
          <p className="text-sm text-ink-dim">{t('schedule.loading')}</p>
          <div className={`${COLUMNS} max-lg:grid-cols-1`}>
            {Array.from({ length: 7 }, (_, index) => (
              <div key={index} className={index > 0 ? 'max-lg:hidden' : undefined}>
                <ScheduleDayPlaceholder />
              </div>
            ))}
          </div>
        </>
      ) : schedule.isError ? (
        <RequestFailed error={schedule.error} lead={t('schedule.readFailed')} />
      ) : week?.problem ? (
        <TmdbNotice problem={week.problem} detail={week.detail} onRetry={retry} />
      ) : subscribedOnly && cards.length === 0 ? (
        <p className="text-sm text-ink-dim">
          {t('schedule.noneSubscribed')}{' '}
          <Link to="/" className={INLINE_LINK}>
            {t('schedule.toDiscover')}
          </Link>
        </p>
      ) : (
        <>
          {/* 窄版：一次一天。日期鍵是一組單選，按下的那一顆是重線加 `deck` 底（不靠顏色）。 */}
          <div
            role="group"
            aria-label={t('schedule.pickDay')}
            className="flex flex-wrap gap-2 lg:hidden"
          >
            {days.map((day) => (
              <button
                key={day}
                type="button"
                aria-pressed={day === shownDay}
                onClick={() => setPicked(day)}
                className={day === shownDay ? FILTER_ACTIVE : FILTER}
              >
                {weekday(day, i18n.language, 'short')}
                {day === today && (
                  <span className="ml-1.5 text-ink-dim">{t('schedule.today')}</span>
                )}
              </button>
            ))}
          </div>
          <div data-testid="schedule-day" className="lg:hidden">
            <ScheduleDay day={shownDay} today={today} cards={cards} />
          </div>
          <div data-testid="schedule-week" className={`${COLUMNS} max-lg:hidden`}>
            {days.map((day) => (
              <ScheduleDay key={day} day={day} today={today} cards={cards} compact />
            ))}
          </div>
        </>
      )}

      <TmdbAttribution />
    </div>
  )
}

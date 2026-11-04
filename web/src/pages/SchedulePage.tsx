import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
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

/**
 * 七欄並排要頁面這一欄至少 60rem 寬，更窄時一次一天。看的是**這一欄**的寬（container query），不是視窗：
 * 1280 寬打開側面板時頁面只剩約 51rem，七欄一欄 106px，季集與評分會疊進隔壁欄（M5.5 票 19 量到 7–22px）。
 * 60rem 時一欄約 127px（1440 寬開面板時量到 129px，放得下）。
 */
const COLUMNS = 'grid gap-3 @min-[60rem]:grid-cols-7'

/**
 * 時間表 `/schedule`（M5.5 票 09，`.scratch/m5.5/schedule-shape.md`）：這一週 TMDB 上播的動畫，版面照
 * AutoBangumi Calendar（brief §20.3）——週一到週日分欄、今天標出。與它不同的是**預設列全部**：這一頁是拿來
 * 找新番的，訂了的再切「只看已訂閱」。
 *
 * 寬的時候（頁面這一欄 60rem 以上）七欄一起看；窄版一次一天，上面一排七顆日期鍵，預設今天。「今天」照伺服器的時區
 * （後端的 `today`），不照瀏覽器：週界與哪一天的欄是同一個時鐘算的。
 */
export function SchedulePage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const schedule = useQuery(scheduleQueryOptions)
  const search = useSearch({ from: '/schedule' })
  const navigate = useNavigate({ from: '/schedule' })
  const subscribedOnly = search.subscribed === true
  // `replace`：換一天、切篩選不堆歷史，上一頁仍回到來這一頁之前的地方。
  const updateSearch = (next: { day?: string; subscribed?: true }) =>
    void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true })

  const week = schedule.data
  const days = week ? weekDays(week.start) : []
  const today = week?.today ?? ''
  const shownDay = search.day && days.includes(search.day) ? search.day : today
  const cards = (week?.cards ?? []).filter(
    (card) => !subscribedOnly || card.status !== 'unsubscribed',
  )
  const retry = () => void queryClient.invalidateQueries({ queryKey: ['schedule'] })

  return (
    <div className="@container mx-auto grid w-full max-w-[110rem] gap-6 px-6 py-8">
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
          onClick={() => updateSearch({ subscribed: subscribedOnly ? undefined : true })}
          className={subscribedOnly ? FILTER_ACTIVE : FILTER}
        >
          {t('schedule.subscribedOnly')}
        </button>
      </div>

      {schedule.isPending ? (
        <>
          {/* 第一次打開要讀這一週每一部的詳情（約 160 部），幾秒到十幾秒；之後六小時內是即時的。 */}
          <p className="text-sm text-ink-dim">{t('schedule.loading')}</p>
          <div className={COLUMNS}>
            {Array.from({ length: 7 }, (_, index) => (
              <div key={index} className={index > 0 ? '@max-[60rem]:hidden' : undefined}>
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
            className="flex flex-wrap gap-2 @min-[60rem]:hidden"
          >
            {days.map((day) => (
              <button
                key={day}
                type="button"
                aria-pressed={day === shownDay}
                onClick={() => updateSearch({ day: day === today ? undefined : day })}
                className={day === shownDay ? FILTER_ACTIVE : FILTER}
              >
                {weekday(day, i18n.language, 'short')}
                {day === today && (
                  <span className="ml-1.5 text-ink-dim">{t('schedule.today')}</span>
                )}
              </button>
            ))}
          </div>
          <div data-testid="schedule-day" className="@min-[60rem]:hidden">
            <ScheduleDay day={shownDay} today={today} cards={cards} />
          </div>
          <div data-testid="schedule-week" className={`${COLUMNS} @max-[60rem]:hidden`}>
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

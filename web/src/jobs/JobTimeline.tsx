import { useTranslation } from 'react-i18next'

import type { JobEvent } from '../api/jobs'
import { Timestamp } from '../components/Timestamp'

/**
 * 一筆 Job 的時間線（brief §5.2、`.scratch/m1/jobs-shape.md` §6）。
 *
 * 每一筆事件一行：型別的中性色塊 + 時間 + **那一個型別自己的那幾格**。
 * 不做通用的 key/value 傾印——那會把 `trigger: manual` 這種已經在列上的東西再說一次，
 * 而且會在畫面上長出一堆沒有人在意的欄位名（shape brief §8）。
 */
export function JobTimeline({ events }: { events: readonly JobEvent[] }) {
  const { t } = useTranslation()

  if (events.length === 0) {
    return <p className="text-xs text-ink-dim">{t('jobs.timeline.empty')}</p>
  }

  return (
    <ol className="grid gap-2">
      {events.map((event) => (
        <li key={event.id} className="grid gap-1 border-l-2 border-rule pl-3">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {/* 事件型別是**分類**不是狀態，所以中性色塊（The Role Is Not A State Rule）。 */}
            <span className="label bg-deck px-1.5 py-1 text-ink">{label(t, event.type)}</span>
            <span className="text-xs text-ink-dim">
              <Timestamp at={event.created_at} />
            </span>
          </p>
          <Facts event={event} />
        </li>
      ))}
    </ol>
  )
}

/**
 * 一筆事件說得出來的那幾格。
 *
 * 型別是後端的封閉集合（`domain.EventType`），所以這裡也是一個窮舉——後端加了新的型別
 * 而前端還沒跟上時，那一行只剩色塊與時間，不會印出一條 i18n key。
 */
function Facts({ event }: { event: JobEvent }) {
  const { t } = useTranslation()
  const payload = event.payload

  if (event.type === 'created') {
    // trigger **不重覆**：它已經是列上的那塊中性色塊，而 payload 裡是未翻譯的原值。
    // 留下的是 route 的 slug——它與下一筆的 `berth-<slug>` 是同一個字，兩行讀得起來。
    return <Row>{text(payload.route) && `route=${text(payload.route)}`}</Row>
  }
  if (event.type === 'submitted') {
    return (
      <>
        <Row>{text(payload.category)}</Row>
        <Row>{text(payload.save_path)}</Row>
      </>
    )
  }
  if (event.type === 'submit_failed') {
    // 服務回的原文，不翻譯（與精靈的纜繩同一個規矩）。用 `blocked-ink` 而不是色塊——
    // 這是一句字，不是一個狀態格。
    return <p className="value text-xs break-words text-blocked-ink">{text(payload.error)}</p>
  }
  if (event.type === 'retried') {
    return <p className="max-w-prose text-xs text-ink-dim">{t('jobs.timeline.retried')}</p>
  }
  return null
}

function Row({ children }: { children: string }) {
  if (!children) return null
  return <p className="value text-xs break-words text-ink-dim">{children}</p>
}

/** 型別的顯示名。認不得的型別原樣顯示——它仍然是一件真的發生過的事。 */
function label(t: (key: string) => string, type: string): string {
  const known = ['created', 'submitted', 'submit_failed', 'retried']
  return known.includes(type) ? t(`jobs.event.${type}`) : type
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { JobEvent } from '../api/jobs'
import { Timestamp } from '../components/Timestamp'
import type { ReviewReason } from '../api/plans'
import { formatSize } from '../media/searchResult'
import { formatPercent } from './jobState'

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
 * 認得的事件型別（`domain.EventType`）。
 *
 * **一份清單，兩個用途**：`FACTS` 的鍵型別由它產生，所以少寫一個 renderer 會在 `tsc` 就紅；
 * `label()` 也讀它，所以「有沒有那一句顯示名」與「畫不畫得出那幾格」不會分岔。
 * 票 11 加 `plan_generated` 時，型別檢查會直接指到還沒補的那一格。
 */
const EVENT_TYPES = [
  'created',
  'submitted',
  'submit_failed',
  'retried',
  'metadata_received',
  'progress',
  'stalled',
  'completed',
  'issue_detected',
  'preplan',
  'plan_generated',
  'review_required',
] as const

type KnownEvent = (typeof EVENT_TYPES)[number]

type Translate = ReturnType<typeof useTranslation>['t']

interface Facing {
  t: Translate
  locale: string
  payload: JobEvent['payload']
}

/**
 * 逐型別那幾格。**窮舉而不是通用傾印**：後端加了新的型別而前端還沒跟上時，
 * 那一行只剩色塊與時間，不會印出一條 i18n key。
 */
const FACTS: Record<KnownEvent, (facing: Facing) => ReactNode> = {
  // trigger **不重覆**：它已經是列上的那塊中性色塊，而 payload 裡是未翻譯的原值。
  // 留下的是 route 的 slug——它與下一筆的 `berth-<slug>` 是同一個字，兩行讀得起來。
  created: ({ payload }) => <Row>{text(payload.route) && `route=${text(payload.route)}`}</Row>,
  submitted: ({ payload }) => (
    <>
      <Row>{text(payload.category)}</Row>
      <Row>{text(payload.save_path)}</Row>
    </>
  ),
  // 服務回的原文，不翻譯（與精靈的纜繩同一個規矩）。用 `blocked-ink` 而不是色塊——
  // 這是一句字，不是一個狀態格。
  submit_failed: ({ payload }) => (
    <p className="value text-xs break-words text-blocked-ink">{text(payload.error)}</p>
  ),
  retried: ({ t }) => (
    <p className="max-w-prose text-xs text-ink-dim">{t('jobs.timeline.retried')}</p>
  ),
  metadata_received: ({ t, locale, payload }) => (
    <Row>
      {t('jobs.timeline.files', {
        count: number(payload.file_count),
        size: formatSize(number(payload.total_size), locale),
      })}
    </Row>
  ),
  // 恢復的那一筆多一句話：它與「又跨了 25%」在時間線上長得一樣，但意思是相反的
  // ——一個說「還在跑」，一個說「它不再卡住了」。
  progress: ({ t, locale, payload }) => (
    <Row>
      {join([
        formatPercent(number(payload.progress), locale),
        payload.resumed === true ? t('jobs.timeline.resumed') : '',
      ])}
    </Row>
  ),
  stalled: ({ t, payload }) => (
    <Row>
      {join([
        t('jobs.timeline.idle', { count: number(payload.idle_minutes) }),
        text(payload.client_state),
      ])}
    </Row>
  ),
  completed: ({ locale, payload }) => <Row>{formatSize(number(payload.total_size), locale)}</Row>,
  // 服務回的原文那一條規矩的另一半：**理由翻譯**。`type` 是封閉集合（`domain.IssueType`），
  // 所以逐種一句話；`client_state` 是機器字串，原樣接在後面。
  issue_detected: ({ t, payload }) => {
    const kind = ISSUES.find((known) => known === payload.type)
    if (!kind) return null
    return (
      <p className="max-w-prose text-xs break-words text-blocked-ink">
        {join([t(`jobs.timeline.issue.${kind}`), text(payload.client_state)])}
      </p>
    )
  },
  // 計劃那三筆共用同一組計數：它們說的是同一件事（這一份計劃長什麼樣），差別在
  // 它是預估、是結論、還是停下來等人。逐檔的決定在展開區的計劃那一塊，不在時間線上。
  preplan: ({ t, payload }) => <Row>{planned(t, payload)}</Row>,
  plan_generated: ({ t, payload }) => <Row>{planned(t, payload)}</Row>,
  // **理由翻譯**（封閉集合 `domain.ReviewReason`），而且是**短的那一種**：時間線說的是
  // 「當時為什麼停下來」，該怎麼辦那一句在計劃那一塊。同一句話說兩次的話，重跑過一次
  // 之後畫面上會有兩個互相矛盾的理由。
  review_required: ({ t, payload }) => {
    const reason = REVIEW_REASONS.find((known) => known === payload.reason)
    return (
      <Row>{join([planned(t, payload), reason ? t(`jobs.timeline.review.${reason}`) : ''])}</Row>
    )
  },
}

/** `domain.ReviewReason` 的三種。認不得的不畫——它可能是後端加的，而前端還沒有那句話。 */
const REVIEW_REASONS: readonly ReviewReason[] = [
  'low_confidence',
  'medium_not_allowed',
  'nothing_to_import',
]

/**
 * 計劃那三筆共用的一行：幾個檔案要入庫，逐信心幾個。
 *
 * 用的是**計劃那一塊的那兩把鍵**（`jobs.plan.*`）：時間線上那一行與展開區的抬頭說的是
 * 同一件事，兩份字面一樣的翻譯遲早會有一份被改掉。
 */
function planned(t: Translate, payload: JobEvent['payload']): string {
  return join([
    t('jobs.plan.planned', { count: number(payload.files) }),
    t('jobs.plan.levels', {
      high: number(payload.high),
      medium: number(payload.medium),
      low: number(payload.low),
    }),
  ])
}

function Facts({ event }: { event: JobEvent }) {
  const { t, i18n } = useTranslation()
  const known = EVENT_TYPES.find((row) => row === event.type)
  if (!known) return null
  return <>{FACTS[known]({ t, locale: i18n.language, payload: event.payload })}</>
}

/**
 * `domain.IssueType` 的四種。認不得的不畫——它可能是後端加的，而前端還沒有那句話。
 *
 * `as const` 不是形式：i18n 的 key 是型別化的，少寫一句話會在 `tsc` 就紅，
 * 不會變成畫面上一條 `jobs.timeline.issue.xxx`。
 */
const ISSUES = ['missing_files', 'client_error', 'client_removed', 'unknown_torrent'] as const

function Row({ children }: { children: string }) {
  if (!children) return null
  return <p className="value text-xs break-words text-ink-dim">{children}</p>
}

/** 型別的顯示名。認不得的型別原樣顯示——它仍然是一件真的發生過的事。 */
function label(t: Translate, type: string): string {
  const known = EVENT_TYPES.find((row) => row === type)
  return known ? t(`jobs.event.${known}`) : type
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function number(value: unknown): number {
  return typeof value === 'number' ? value : 0
}

/**
 * 一行裡的幾格，中點分隔。空的那幾格不留分隔符——「· ·」讀起來像少了一個值。
 *
 * 與列上的 `Dot` 是同一種分隔，但這裡是純字串：時間線的每一格都是文字，
 * 而 `Dot` 是給有元素邊界的那種列用的。
 */
function join(parts: readonly string[]): string {
  return parts.filter(Boolean).join(' · ')
}

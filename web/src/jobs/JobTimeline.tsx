import type { ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { JobEvent } from '../api/jobs'
import type { Signal } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import type { ReviewReason } from '../api/plans'
import { formatSize } from '../media/searchResult'
import { JOB_SIGNAL, formatPercent } from './jobState'

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
      {runs(events).map((run) => {
        const last = run[run.length - 1]
        return (
          <li key={run[0].id} className="grid min-w-0 gap-1 border-l-2 border-rule pl-3">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {/* 事件型別是**分類**不是狀態，所以中性色塊（The Role Is Not A State Rule）。 */}
              <span className="label bg-deck px-1.5 py-1 text-ink">{label(t, last.type)}</span>
              {run.length > 1 && (
                <span className="value text-xs text-ink">
                  {t('jobs.timeline.linkedFiles', { count: run.length })}
                </span>
              )}
              <span className="text-xs text-ink-dim">
                <Timestamp at={last.created_at} />
              </span>
            </p>
            {run.length === 1 ? (
              <Facts event={last} />
            ) : (
              <details className="min-w-0">
                <summary className="label cursor-pointer text-ink-dim">
                  {t('jobs.timeline.linkedTargets')}
                </summary>
                <ol className="mt-1 grid gap-0.5">
                  {run.map((event) => (
                    <li key={event.id}>
                      <Row>{text(event.payload.target)}</Row>
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </li>
        )
      })}
    </ol>
  )
}

/**
 * 把連續的 `linked` 收成一段，其餘事件各自一段。
 *
 * 一個檔案一筆 `linked`（票 12），一季 39 個檔案展開之後就是 39 行只差一條路徑的「已鏈接」，
 * 把這一筆之後發生的事推到幾千 px 以下（票 15 的 critique）。它們是同一件事的逐檔證據：
 * 一行說「鏈接了幾個」，路徑收在底下要看才展開。中間夾著別的事件就是另一段——時間線的順序不動。
 */
function runs(events: readonly JobEvent[]): JobEvent[][] {
  const out: JobEvent[][] = []
  for (const event of events) {
    const previous = out[out.length - 1]
    if (event.type === 'linked' && previous?.[0].type === 'linked') previous.push(event)
    else out.push([event])
  }
  return out
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
  'linked',
  'link_failed',
  'jellyfin_scan_requested',
  'jellyfin_item_resolved',
  'jellyfin_request_failed',
  'deleted',
  'audit_confirmed',
  'audit_undone',
] as const

type KnownEvent = (typeof EVENT_TYPES)[number]

// `TFunction` 而不是 `ReturnType<typeof useTranslation>['t']`：後者要把整棵鍵樹再展開一次，
// 票 13 多了媒體庫的鍵之後 tsc 報「型別展開太深」（TS2589）。兩者對呼叫端是同一個型別。
type Translate = TFunction

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
    <p className="value text-xs wrap-anywhere text-blocked-ink">{text(payload.error)}</p>
  ),
  // 兩種重試回到的站不同：送單的重試退回「已建立」再送一次，入庫的重試退回「入庫中」
  // 從沒鏈接的檔案接著做（票 12）。`state` 是後端寫的，不是前端猜的。
  retried: ({ t, payload }) => (
    <p className="max-w-prose text-xs text-ink-dim">
      {payload.state === 'importing'
        ? t('jobs.timeline.retriedImport')
        : t('jobs.timeline.retried')}
    </p>
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
    // 紅字只給擋住這一筆的：與列上的狀態色塊查同一張表（`JOB_SIGNAL`）。torrent 從客戶端消失、
    // 不認得的 torrent、Jellyfin 還沒列出都是要人看一眼的事，不是阻擋（The One Meaning Rule）。
    const blocking = (JOB_SIGNAL as Partial<Record<string, Signal>>)[kind] === 'blocked'
    return (
      <p
        className={`max-w-prose text-xs break-words ${blocking ? 'text-blocked-ink' : 'text-ink'}`}
      >
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
  // 入庫那幾筆（票 12）。一個檔案一筆 `linked`，所以它只帶**目標**——來源檔名在計劃那一塊，
  // 同一行印兩條長路徑會讓一季的時間線寬到讀不動。
  linked: ({ payload }) => <Row>{text(payload.target)}</Row>,
  // **擋住入庫的才是紅字**（The One Meaning Rule）：正片進不了庫是阻擋，一條字幕或一個特典
  // 沒鏈上不是（票 12）。擋不擋由後端判定（`blocking`），前端不重算一份規則。
  link_failed: ({ payload }) => (
    <>
      <Row>{text(payload.target)}</Row>
      <p
        className={`value text-xs wrap-anywhere ${payload.blocking === true ? 'text-blocked-ink' : 'text-ink-dim'}`}
      >
        {text(payload.error)}
      </p>
    </>
  ),
  jellyfin_scan_requested: ({ t, payload }) => (
    <Row>{t('jobs.timeline.scanRequested', { count: number(payload.count) })}</Row>
  ),
  jellyfin_item_resolved: ({ t, payload }) => (
    <Row>{t('jobs.timeline.resolved', { count: number(payload.count) })}</Row>
  ),
  // **不是紅字**：這種失敗不擋入庫（檔案已經在媒體庫裡了），紅色只代表阻擋
  // （The One Meaning Rule）。理由翻譯、原文接在後面，與 `issue_detected` 同一個規矩。
  jellyfin_request_failed: ({ t, payload }) => {
    const request = JELLYFIN_REQUESTS.find((known) => known === payload.request)
    return (
      <p className="max-w-prose text-xs break-words text-ink-dim">
        {join([request ? t(`jobs.timeline.jellyfin.${request}`) : '', text(payload.error)])}
      </p>
    )
  },
  // 刪除範圍跑完（brief §9.2、M2 票 04）。說的是**真的做掉了什麼**而不是勾了哪幾個：
  // 勾了「移除鏈接」而那幾個檔案早就被人刪掉時，這裡是「0 個鏈接」。空出來的位元組另
  // 起一行，因為它才是使用者按下去時想知道的那一件事。
  deleted: ({ t, locale, payload }) => (
    <>
      <Row>
        {join([
          t('jobs.timeline.deletedLinks', { count: number(payload.links) }),
          t('jobs.timeline.deletedSources', { count: number(payload.sources) }),
          payload.torrent === true ? t('jobs.timeline.deletedTorrent') : '',
          payload.purged === true ? t('jobs.timeline.deletedPurged') : '',
        ])}
      </Row>
      <Row>
        {number(payload.freed) > 0
          ? t('jobs.timeline.freed', { size: formatSize(number(payload.freed), locale) })
          : t('jobs.timeline.freedNothing')}
      </Row>
    </>
  ),
  // audit 的兩顆（M2 票 06）。句子說誰做了什麼，目標路徑是機器字串，另起一行。撤銷那一句照
  // `unlinked` 說**真的**拆到了沒——撤銷之前有人已經在 Jellyfin 裡刪掉它的話，沒有東西可拆。
  audit_confirmed: ({ t, payload }) => (
    <>
      <p className="max-w-prose text-xs text-ink-dim">{t('jobs.timeline.auditConfirmed')}</p>
      <Row>{text(payload.target)}</Row>
    </>
  ),
  audit_undone: ({ t, payload }) => (
    <>
      <p className="max-w-prose text-xs text-ink-dim">
        {payload.unlinked === false
          ? t('jobs.timeline.auditUndoneGone')
          : t('jobs.timeline.auditUndone')}
      </p>
      <Row>{text(payload.target)}</Row>
    </>
  ),
}

/** `domain.JellyfinRequest`。認不得的只印原文——它可能是後端加的，而前端還沒有那句話。 */
const JELLYFIN_REQUESTS = ['scan'] as const

/** `domain.ReviewReason` 的五種。認不得的不畫——它可能是後端加的，而前端還沒有那句話。 */
const REVIEW_REASONS: readonly ReviewReason[] = [
  'low_confidence',
  'medium_not_allowed',
  'nothing_to_import',
  'target_exists',
  'audit_undone',
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
 * `domain.IssueType` 的五種。認不得的不畫——它可能是後端加的，而前端還沒有那句話。
 *
 * `as const` 不是形式：i18n 的 key 是型別化的，少寫一句話會在 `tsc` 就紅，
 * 不會變成畫面上一條 `jobs.timeline.issue.xxx`。
 */
const ISSUES = [
  'missing_files',
  'client_error',
  'client_removed',
  'unknown_torrent',
  'jellyfin_item_unresolved',
] as const

function Row({ children }: { children: string }) {
  if (!children) return null
  return <p className="value text-xs wrap-anywhere text-ink-dim">{children}</p>
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

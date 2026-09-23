import type { ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { JobEvent } from '../api/jobs'
import type { Signal } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import type { PlanAction, ReviewReason } from '../api/plans'
import { formatEpisode } from '../components/episodes'
import { formatSize } from '../media/searchResult'
import { EVENT_TYPES, type KnownEvent } from './eventTypes'
import { JOB_SIGNAL, formatPercent } from './jobState'

/**
 * 一筆 Job 的時間線（brief §5.2、`.scratch/m1/jobs-shape.md` §6）。
 *
 * 每一筆事件一行：型別的中性色塊 + 時間 + **那一個型別自己的那幾格**。
 * 不做通用的 key/value 傾印——那會把 `trigger: manual` 這種已經在列上的東西再說一次，
 * 而且會在畫面上長出一堆沒有人在意的欄位名（shape brief §8）。
 */
export function JobTimeline({
  events,
  latest,
}: {
  events: readonly JobEvent[]
  /**
   * 只畫最近幾段（`/jobs` 展開區的摘要，M2 票 12）。完整的一份在詳情頁；**較早的筆數算的是事件**，
   * 不是段——連續的鏈接收成一段，但詳情頁上要看的是那幾筆。
   */
  latest?: number
}) {
  const { t } = useTranslation()

  if (events.length === 0) {
    return <p className="text-xs text-ink-dim">{t('jobs.timeline.empty')}</p>
  }

  const all = runs(events)
  const shown = latest === undefined ? all : all.slice(-latest)
  const earlier = events.length - shown.reduce((sum, run) => sum + run.length, 0)

  return (
    <div className="grid gap-2">
      {earlier > 0 && (
        <p className="text-xs text-ink-dim">{t('jobs.timeline.earlier', { count: earlier })}</p>
      )}
      <ol className="grid gap-2">
        {shown.map((run) => {
          const last = run[run.length - 1]
          return (
            <li key={run[0].id} className="grid min-w-0 gap-1 border-l-2 border-rule pl-3">
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                {/* 事件型別是**分類**不是狀態，所以中性色塊（The Role Is Not A State Rule）。 */}
                <span className="label bg-deck px-1.5 py-1 text-ink">{label(t, last)}</span>
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
    </div>
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
  // 重試回到的站不同：送單的重試退回「已建立」再送一次，入庫的重試退回「入庫中」從沒鏈接的
  // 檔案接著做（票 12）；待處理上的幾顆各有自己的一句（M2 票 09、09c）。`state` 與 `action`
  // 是後端寫的，不是前端猜的。
  retried: ({ t, payload }) => (
    <p className="max-w-prose text-xs text-ink-dim">{t(retriedText(payload))}</p>
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
  // 核准或拒絕（M2 票 07）。拒絕之後規劃器整份重算，所以緊接著的就是新的那一份的 `review_required`
  // 或 `plan_generated`——這一行只要說出誰決定了什麼。
  review_decided: ({ t, payload }) => (
    <p className="max-w-prose text-xs text-ink-dim">
      {payload.decision === 'approved'
        ? t('jobs.timeline.reviewApproved', { count: number(payload.files) })
        : t('jobs.timeline.reviewRejected')}
    </p>
  ),
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
  // rematch（M2 票 08）：誰改的在列上（actor），這一行說從什麼改成什麼——處置加季集，路徑是機器
  // 字串，舊的與新的各一行。不在媒體庫裡的那一邊沒有路徑可印。
  rematched: ({ t, payload }) => {
    const from = stateOf(payload.from)
    const to = stateOf(payload.to)
    return (
      <>
        <p className="max-w-prose text-xs text-ink-dim">
          {t('jobs.timeline.rematched', { from: describe(t, from), to: describe(t, to) })}
        </p>
        <Row>{text(payload.file)}</Row>
        <Row>{from.target && `${from.target} →`}</Row>
        <Row>{to.target}</Row>
      </>
    )
  },
  // 規劃時略過的重複版本（brief §7.8）。每一個在審核佇列上是一列，這裡只說有幾個、是哪幾個。
  duplicate_skipped: ({ t, payload }) => {
    const files = Array.isArray(payload.files) ? payload.files.map(text).filter(Boolean) : []
    return (
      <>
        <p className="max-w-prose text-xs text-ink-dim">
          {t('jobs.timeline.duplicateSkipped', { count: files.length })}
        </p>
        {files.map((file) => (
          <Row key={file}>{file}</Row>
        ))}
      </>
    )
  },
  duplicate_decided: ({ t, payload }) => {
    const decision = DUPLICATE_DECISIONS.find((known) => known === payload.decision)
    return (
      <>
        {decision && (
          <p className="max-w-prose text-xs text-ink-dim">
            {t(`jobs.timeline.duplicateDecided.${decision}`)}
          </p>
        )}
        <Row>{text(payload.target) || text(payload.file)}</Row>
      </>
    )
  },
}

/** `domain.DuplicateDecision`。認不得的不畫那一句——它可能是後端加的，而前端還沒有那句話。 */
const DUPLICATE_DECISIONS = ['replace', 'keep_both', 'skip'] as const

/** `domain.PlanAction`：rematch 那一行的處置。 */
const PLAN_ACTIONS: readonly PlanAction[] = [
  'import',
  'extra',
  'subtitle',
  'skip',
  'unmatched',
  'review',
]

interface FileState {
  action: PlanAction | null
  season: number | null
  episode_start: number | null
  episode_end: number | null
  target: string
}

/** rematch 那一筆的 `from` / `to`（`{action, season, episode_start, episode_end, target}`）。 */
function stateOf(value: unknown): FileState {
  const row = (typeof value === 'object' && value !== null ? value : {}) as Record<string, unknown>
  const count = (key: string) => (typeof row[key] === 'number' ? (row[key] as number) : null)
  return {
    action: PLAN_ACTIONS.find((known) => known === row.action) ?? null,
    season: count('season'),
    episode_start: count('episode_start'),
    episode_end: count('episode_end'),
    target: text(row.target),
  }
}

/** 「特典」「正片 S00E03」「略過」：處置的名字加它蓋到的集（與計劃那一塊同一套詞）。 */
function describe(t: Translate, state: FileState): string {
  const action = state.action ? t(`jobs.plan.action.${state.action}`) : ''
  return [action, formatEpisode(state)].filter(Boolean).join(' ') || t('jobs.timeline.notInLibrary')
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

function Row({ children }: { children: string | false }) {
  if (!children) return null
  return <p className="value text-xs wrap-anywhere text-ink-dim">{children}</p>
}

/**
 * 型別的顯示名。認不得的型別原樣顯示——它仍然是一件真的發生過的事。
 *
 * 重新入庫記成 `retried` + `action: reimport`（`services/reimport.py`），但對使用者它不是
 * 「重試」：那一筆沒有失敗過，是管理員要它照 complete 重來一次。
 */
function label(t: Translate, event: JobEvent): string {
  if (event.type === 'retried' && event.payload.action === 'reimport') {
    return t('jobs.trigger.reimport')
  }
  const known = EVENT_TYPES.find((row) => row === event.type)
  return known ? t(`jobs.event.${known}`) : event.type
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

function retriedText(payload: Record<string, unknown>) {
  if (payload.action === 'recheck') return 'jobs.timeline.retriedRecheck'
  if (payload.action === 'retry') return 'jobs.timeline.retriedRestart'
  if (payload.action === 'reimport') return 'jobs.timeline.retriedReimport'
  if (payload.state === 'importing') return 'jobs.timeline.retriedImport'
  if (payload.state === 'completed') return 'jobs.timeline.retriedReplan'
  return 'jobs.timeline.retried'
}

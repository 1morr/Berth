import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isJobRefusal } from '../api/jobs'
import { mediaQueryOptions } from '../api/media'
import { routesQueryOptions } from '../api/routes'
import { isRssRefusal } from '../api/rss'
import {
  decideProposal,
  proposalRefusalOf,
  proposalsKey,
  WAITING,
  type Proposal,
  type ProposalRow,
  type RouteAsk,
} from '../api/proposals'
import { Checkbox, CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import i18n from '../i18n'
import { formatList } from '../i18n/list'
import { formatSize } from '../media/searchResult'
import { useCardActions } from './cards'

/**
 * 確認卡（M5 票 13、brief §14〈對話裡的確認卡〉）：畫在提出它的那一格工具呼叫上。
 *
 * **長相由命令決定，不由模型決定**：命令名挑列的畫法（`RowBody`），效果與期限是伺服器提出時算的
 * （`preview`、`expires_at`）。一列是單項卡，列出欄位；多列是總覽卡，逐列可取消勾選。
 *
 * **按下去就做**：核准的回應裡就是逐列結果（會部分成功），畫在每一列上。之後才告訴對話（`respond`），
 * 讓助理接著說。
 *
 * **作品放得進的 Route 不只一條時，那一列的 Route 由人選**（票 23b）：清單是伺服器提出時存的
 * （`preview.routes`），預選這部作品上次用的那一條、沒用過就不預選；勾著的列沒選齊之前確認鍵不畫
 * （DESIGN.md「先選再確認」），伺服器也只收清單裡的。
 */
export function ConfirmCard({ proposal, toolCallId }: { proposal: Proposal; toolCallId: string }) {
  const { t } = useTranslation()
  const titleId = useId()
  const queryClient = useQueryClient()
  const { respond } = useCardActions()
  const rows = proposal.arguments
  const [ticked, setTicked] = useState<ReadonlySet<number>>(() => new Set(rows.keys()))
  const waiting = WAITING.has(proposal.status)
  const many = rows.length > 1
  const asks = proposal.preview.routes
  const asking = asks.some((ask) => ask !== null)
  const [picks, setPicks] = useState<readonly (number | null)[]>(() =>
    rows.map((_, index) => asks[index]?.preselected ?? null),
  )
  // 勾著、而且作品放得進的 Route 不只一條的列：要人選。
  const choosing = (index: number) => asks[index] != null && ticked.has(index)
  const unpicked = rows.filter((_, index) => choosing(index) && picks[index] === null).length
  // 按過之後整排鍵收掉：焦點交給卡片標題，不掉回 `body`（WCAG 2.4.3）。只在這一頁按的才搬。
  const title = useRef<HTMLHeadingElement>(null)
  const pressed = useRef(false)
  useEffect(() => {
    if (!waiting && pressed.current) {
      pressed.current = false
      title.current?.focus()
    }
  }, [waiting])

  const decide = useMutation({
    mutationFn: (approve: boolean) =>
      decideProposal(proposal.id, {
        approve,
        // 全勾就是「全部」：不帶勾選，與單項卡同一個形狀。
        selection:
          approve && many && ticked.size < rows.length ? [...ticked].sort((a, b) => a - b) : null,
        // 沒勾的列不送它的 Route：伺服器只要勾著的那幾列選齊。
        ...(approve && asking
          ? {
              routes: rows.map((_, index) => (choosing(index) ? picks[index] : null)),
            }
          : {}),
      }),
    onSuccess: async (decided) => {
      queryClient.setQueryData<Proposal[]>(proposalsKey(proposal.conversation_id ?? ''), (old) =>
        old?.map((card) => (card.id === decided.id ? decided : card)),
      )
      await respond(toolCallId, decided)
    },
    onError: async (error) => {
      // 送不出去時卡片還在等、鍵還在：不搬焦點。被拒（已經有人按過、過期）的會重畫成結果，照樣搬。
      const refused = proposalRefusalOf(error) !== null
      pressed.current = refused
      // 已經有人按過或剛好過期：問一次它現在的樣子，卡片照那個畫。
      if (refused) {
        await queryClient.invalidateQueries({
          queryKey: proposalsKey(proposal.conversation_id ?? ''),
        })
      }
    },
  })
  const refusal = proposalRefusalOf(decide.error)

  return (
    <section
      aria-labelledby={titleId}
      className={`grid min-w-0 gap-3 border-2 p-3 ${waiting ? 'border-rule-strong bg-well' : 'border-rule bg-hull'}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {waiting ? (
          <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.assigned}`}>
            {t('agent.card.label')}
          </span>
        ) : null}
        <h3 ref={title} id={titleId} tabIndex={-1} className="min-w-0 flex-1 text-sm text-ink">
          {commandTitle(proposal.command)}
        </h3>
      </div>

      <Effects proposal={proposal} />
      {waiting && asking ? <p className="text-xs text-ink">{t('agent.card.routeLead')}</p> : null}
      {proposal.command === SUBMIT ? <SubmitFolders rows={rows} /> : null}

      <ol className="grid gap-2">
        {rows.map((row, index) => {
          const ticking = waiting && many
          const ask = asks[index] ?? null
          const body = (
            <RowBody
              command={proposal.command}
              row={row}
              labelled={ticking}
              external={proposal.preview.external_fields[index] ?? []}
              torrents={proposal.preview.torrents[index]}
              route={{
                ask,
                // 等人按的時候是這一頁的選擇，按過之後是伺服器記下的那一條。
                pick: waiting ? (picks[index] ?? null) : (proposal.routes?.[index] ?? null),
                editable: waiting && !decide.isPending,
                onPick: (route) =>
                  setPicks((old) => old.map((value, at) => (at === index ? route : value))),
              }}
            />
          )
          const result = proposal.results?.[index]
          return (
            // 列沒有自己的 id；位置就是它的身分（卡片的參數存下之後不再變）。
            <li
              key={index}
              className="grid min-w-0 gap-1 border-t-2 border-rule pt-2 first:border-t-0 first:pt-0"
            >
              {ticking ? (
                <Checkbox
                  label={rowLabel(proposal.command, row, index)}
                  checked={ticked.has(index)}
                  disabled={decide.isPending}
                  onChange={(on) =>
                    setTicked((old) => {
                      const next = new Set(old)
                      if (on) next.add(index)
                      else next.delete(index)
                      return next
                    })
                  }
                />
              ) : null}
              {body}
              {result ? <RowResult result={result} command={proposal.command} /> : null}
            </li>
          )
        })}
      </ol>

      {/* 一直掛著：按下去之後的結論要念得到（DESIGN.md 就地確認那一節）。 */}
      <p role="status" className="text-sm text-ink empty:hidden">
        {waiting ? '' : t(`agent.card.status.${proposal.status}`)}
      </p>

      {waiting ? (
        <div className="grid gap-2">
          {proposal.status === 'detached' ? (
            <p className="text-xs text-ink-dim">{t('agent.card.detached')}</p>
          ) : null}
          {refusal ? (
            <p role="alert" className="text-sm text-blocked-ink">
              {t(`agent.card.refusal.${refusal.reason}`)}
            </p>
          ) : decide.error ? (
            <RequestFailed error={decide.error} lead={t('agent.card.failed')} />
          ) : null}
          <div className={CONFIRM_ACTIONS}>
            {ticked.size > 0 && unpicked === 0 ? (
              <PrimaryButton
                type="button"
                // `busy` 而不是 `disabled`：停用的鍵接不住焦點（DESIGN.md〈Buttons〉）。
                busy={decide.isPending}
                onClick={() => {
                  pressed.current = true
                  decide.mutate(true)
                }}
              >
                {decide.isPending && decide.variables
                  ? t('agent.card.running')
                  : many
                    ? t('agent.card.confirmCount', { count: ticked.size })
                    : t('agent.card.confirm')}
              </PrimaryButton>
            ) : (
              // 一列都沒勾、或勾著的列還沒選 Route：按下去必被拒的鍵不畫（DESIGN.md「先選再確認」），
              // 那一格說為什麼。
              <p className="text-xs text-ink-dim">
                {ticked.size === 0
                  ? t('agent.card.noneTicked')
                  : t('agent.card.routeMissing', { count: unpicked })}
              </p>
            )}
            <GhostButton
              type="button"
              busy={decide.isPending}
              onClick={() => {
                pressed.current = true
                decide.mutate(false)
              }}
            >
              {t('agent.card.reject')}
            </GhostButton>
          </div>
        </div>
      ) : null}
    </section>
  )
}

/** 效果（不可逆、會送出 torrent……）與期限：卡片上一定要看得到的兩件事（票面）。 */
function Effects({ proposal }: { proposal: Proposal }) {
  const { t } = useTranslation()
  const effects = [
    ...(proposal.preview.effect === 'irreversible' ? ['irreversible' as const] : []),
    ...proposal.preview.flags.filter((flag) => flag !== 'internal'),
  ]
  return (
    <div className="grid gap-1">
      {effects.length > 0 ? (
        <ul className="flex flex-wrap gap-x-3 gap-y-1">
          {effects.map((effect) => (
            <li key={effect} className="label text-ink">
              {t(`agent.card.effects.${effect}`)}
            </li>
          ))}
        </ul>
      ) : null}
      {proposal.preview.external_fields.some((fields) => fields.length > 0) ? (
        // 只在自由文字出自外部內容的卡上出現（M5 票 14）：每張都亮的話就沒人看了。
        <p className="text-xs text-ink">{t('agent.card.externalLead')}</p>
      ) : null}
      {WAITING.has(proposal.status) ? (
        <p className="text-xs text-ink-dim">
          {t('agent.card.expires')} <Timestamp at={proposal.expires_at} />
        </p>
      ) : null}
      {proposal.preview.held_back > 0 ? (
        <p className="text-xs text-ink-dim">
          {t('agent.card.heldBack', { count: proposal.preview.held_back })}
        </p>
      ) : null}
    </div>
  )
}

/** 卡片的標題：命令的人話名稱，認不得的照原名。 */
const COMMAND_TITLES = {
  'downloading.add_manual_download': 'agent.card.commands.downloading_add_manual_download',
  'rss.subscribe_mikan': 'agent.card.commands.rss_subscribe_mikan',
  'rss.subscribe_search': 'agent.card.commands.rss_subscribe_search',
  'rss.add_feed': 'agent.card.commands.rss_add_feed',
} as const

function commandTitle(command: string): string {
  return Object.hasOwn(COMMAND_TITLES, command)
    ? i18n.t(COMMAND_TITLES[command as keyof typeof COMMAND_TITLES])
    : command
}

type Row = Proposal['arguments'][number]

interface SubmitRow {
  source: { title?: string; size?: number }
  media_id: string
  route_id: number
}

const SUBMIT = 'downloading.add_manual_download'

function isSubmit(command: string, row: Row): row is Row & SubmitRow {
  return command === SUBMIT && typeof row.media_id === 'string'
}

function rowLabel(command: string, row: Row, index: number): string {
  if (isSubmit(command, row)) return row.source.title ?? `#${index + 1}`
  return `#${index + 1}`
}

/**
 * 一列的欄位。送單照結果表的說法（發佈名、大小、作品、Route），RSS 的三種照 RSS 頁的說法；其他命令
 * 列出參數原文。`external` 是出自外部內容的那幾格：在那一格旁邊標出來。
 */
function RowBody({
  command,
  row,
  labelled,
  external,
  torrents,
  route,
}: {
  command: string
  row: Row
  labelled: boolean
  external: readonly string[]
  /** 這一列按下去會送出幾個 torrent；`null` 是要送出時才知道，`undefined` 是不送。 */
  torrents: number | null | undefined
  route: RouteSlot
}) {
  const { t } = useTranslation()
  // `labelled`：勾選框的標籤已經是發佈名，欄位裡不再印一次。
  if (isSubmit(command, row)) return <SubmitRowBody row={row} labelled={labelled} route={route} />
  if (command === 'rss.add_feed') return <FeedRowBody row={row} external={external} />
  if (command === 'rss.subscribe_mikan' || command === 'rss.subscribe_search') {
    return (
      <SubscribeRowBody
        command={command}
        row={row}
        external={external}
        torrents={torrents}
        route={route}
      />
    )
  }
  return (
    <div className="grid gap-1">
      <pre className="value text-xs whitespace-pre-wrap wrap-anywhere text-ink">
        {JSON.stringify(row, null, 2)}
      </pre>
      {external.length > 0 ? (
        <p className="text-xs text-ink">
          {t('agent.card.externalFields', { fields: external.join(', ') })}
        </p>
      ) : null}
    </div>
  )
}

/** 一格：標籤、值，出自外部內容的多一個標記。 */
interface Field {
  name: string
  label: string
  value: ReactNode
  mono?: boolean
}

/** 一列的 Route 那一格（票 23b）：`ask` 不是 `null` 時由人選。 */
interface RouteSlot {
  ask: RouteAsk | null
  /** 選了哪一條；`null` 是還沒選（或沒得選）。 */
  pick: number | null
  editable: boolean
  onPick: (route: number | null) => void
}

/**
 * Route 的值：要人選的列是必選的下拉（清單只有伺服器存下的那幾條），按過之後是選的那一條；
 * 沒得選的列照 `fallback`（模型給、伺服器驗過的那一條）。
 */
function RouteValue({ route, fallback }: { route: RouteSlot; fallback: string }) {
  const { t } = useTranslation()
  const { ask, pick } = route
  if (ask === null) return fallback
  if (!route.editable) return ask.options.find((option) => option.id === pick)?.name ?? '—'
  return (
    <select
      aria-label={t('agent.card.fields.route')}
      required
      value={pick ?? ''}
      onChange={(event) =>
        route.onPick(event.target.value === '' ? null : Number(event.target.value))
      }
      className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
    >
      <option value="">{t('agent.card.routeChoose')}</option>
      {ask.options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.name}
        </option>
      ))}
    </select>
  )
}

function Fields({ fields, external }: { fields: Field[]; external: readonly string[] }) {
  const { t } = useTranslation()
  return (
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
      {fields.map((field) => (
        <div key={field.name} className="contents">
          <dt className="label text-ink-dim">{field.label}</dt>
          <dd className={`wrap-anywhere text-ink ${field.mono ? 'value' : ''}`}>
            {field.value}
            {external.includes(field.name) ? (
              // 提醒、不是阻擋：不用紅（The One Meaning Rule），重線框標出來（The Heavier Line Rule）。
              <span className="label ml-2 inline-block border-2 border-rule-strong px-1 text-ink">
                {t('agent.card.fromOutside')}
              </span>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function text(value: unknown): string {
  return typeof value === 'string' && value.trim() !== '' ? value : '—'
}

/** Route 的名字。加 Feed 只有管理員做得了，所以讀得到 Route 清單。 */
function useRouteName(): (id: unknown) => string {
  const routes = useQuery(routesQueryOptions)
  return (id) => {
    if (typeof id !== 'number') return '—'
    return routes.data?.find((managed) => managed.route.id === id)?.route.name ?? `#${id}`
  }
}

function FeedRowBody({ row, external }: { row: Row; external: readonly string[] }) {
  const { t, i18n: i18nInstance } = useTranslation()
  const routeName = useRouteName()
  const exclusions = Array.isArray(row.exclusions) ? row.exclusions.map(String) : []
  return (
    <Fields
      external={external}
      fields={[
        { name: 'url', label: t('agent.card.fields.url'), value: text(row.url), mono: true },
        { name: 'name', label: t('agent.card.fields.name'), value: text(row.name) },
        {
          name: 'tv_route_id',
          label: t('agent.card.fields.tvRoute'),
          value: routeName(row.tv_route_id),
        },
        {
          name: 'movie_route_id',
          label: t('agent.card.fields.movieRoute'),
          value: routeName(row.movie_route_id),
        },
        ...(exclusions.length > 0
          ? [
              {
                name: 'exclusions',
                label: t('agent.card.fields.exclusions'),
                value: formatList(exclusions, i18nInstance.language),
                mono: true,
              },
            ]
          : []),
      ]}
    />
  )
}

function SubscribeRowBody({
  command,
  row,
  external,
  torrents,
  route,
}: {
  command: 'rss.subscribe_mikan' | 'rss.subscribe_search'
  row: Row
  external: readonly string[]
  torrents: number | null | undefined
  route: RouteSlot
}) {
  const { t } = useTranslation()
  const mediaId = typeof row.media_id === 'string' ? row.media_id : ''
  const media = useQuery({ ...mediaQueryOptions(mediaId), enabled: mediaId !== '' })
  const given = media.data?.routes.find((choice) => choice.id === row.route_id)
  const source: Field[] =
    command === 'rss.subscribe_mikan'
      ? [
          {
            // 番組名是模型給的自由文字（`name`），出自外部內容的話標在這一格。
            name: 'name',
            label: t('agent.card.fields.bangumi'),
            value: text(row.name) === '—' ? `#${String(row.bangumi_id)}` : text(row.name),
          },
          {
            name: 'subgroup_name',
            label: t('agent.card.fields.subgroup'),
            value:
              text(row.subgroup_name) === '—'
                ? `#${String(row.subgroup_id)}`
                : text(row.subgroup_name),
          },
        ]
      : [
          { name: 'kind', label: t('agent.card.fields.site'), value: text(row.kind) },
          { name: 'term', label: t('agent.card.fields.term'), value: text(row.term), mono: true },
        ]
  return (
    <Fields
      external={external}
      fields={[
        ...source,
        {
          name: 'media_id',
          label: t('agent.card.fields.media'),
          value: media.data?.title ?? mediaId,
        },
        {
          name: 'route_id',
          label: t('agent.card.fields.route'),
          value: <RouteValue route={route} fallback={given?.name ?? `#${String(row.route_id)}`} />,
        },
        // 訂閱 Mikan 按下去就當場送整季，不經第一批確認（協調者 2026-10-27）：按的人要知道送多少。
        ...(command === 'rss.subscribe_mikan'
          ? [
              {
                name: 'sends',
                label: t('agent.card.fields.sends'),
                value:
                  typeof torrents === 'number'
                    ? t('agent.card.wholeSeason', { count: torrents })
                    : t('agent.card.wholeSeasonUnknown'),
              },
            ]
          : []),
      ]}
    />
  )
}

function SubmitRowBody({
  row,
  labelled,
  route,
}: {
  row: SubmitRow
  labelled: boolean
  route: RouteSlot
}) {
  const { t, i18n: i18nInstance } = useTranslation()
  // 作品頁的那一份：作品名與這部作品選得了的 Route（Route 名不必另外問）。
  const media = useQuery(mediaQueryOptions(row.media_id))
  const given = media.data?.routes.find((choice) => choice.id === row.route_id)
  return (
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
      {labelled ? null : (
        <>
          <dt className="label text-ink-dim">{t('agent.card.fields.release')}</dt>
          <dd className="value wrap-anywhere text-ink">{row.source.title ?? '—'}</dd>
        </>
      )}
      <dt className="label text-ink-dim">{t('agent.card.fields.size')}</dt>
      <dd className="value text-ink">{formatSize(row.source.size ?? 0, i18nInstance.language)}</dd>
      <dt className="label text-ink-dim">{t('agent.card.fields.media')}</dt>
      <dd className="text-ink">{media.data?.title ?? row.media_id}</dd>
      <dt className="label text-ink-dim">{t('agent.card.fields.route')}</dt>
      <dd className="text-ink">
        <RouteValue route={route} fallback={given?.name ?? `#${row.route_id}`} />
      </dd>
    </dl>
  )
}

/**
 * 送單會寫死的資料夾名（plan §5，票 13 留給票 22）：作品頁的送單確認會重述它，卡片也要——第一次送單
 * 成功那一刻它就定下來，之後改不掉。同一部作品的列只印一次。
 */
function SubmitFolders({ rows }: { rows: readonly Row[] }) {
  const ids = [...new Set(rows.filter((row) => isSubmit(SUBMIT, row)).map((row) => row.media_id))]
  return ids.map((id) => <SubmitFolder key={id} mediaId={id} />)
}

function SubmitFolder({ mediaId }: { mediaId: string }) {
  const { t } = useTranslation()
  const media = useQuery(mediaQueryOptions(mediaId))
  if (!media.data) return null
  return (
    <div className="grid gap-0.5 text-xs">
      <p className="flex flex-wrap gap-x-3 gap-y-0.5">
        <span className="label text-ink-dim">{t('agent.card.fields.folder')}</span>
        {/* 機器字串：原樣出現在檔案系統上。 */}
        <span className="value min-w-0 wrap-anywhere text-ink">
          {media.data.folder_name || '—'}
        </span>
      </p>
      <p className="max-w-prose text-ink-dim">
        {media.data.folder_frozen ? t('submit.alreadyFrozen') : t('submit.willFreeze')}
      </p>
    </div>
  )
}

/** 拒絕理由照命令那一組的句子：送單是 `jobs.refusal`，RSS 的三種是 `rss.refusal`。 */
function refusalSentence(command: string, result: ProposalRow): string | null {
  if (result.outcome !== 'refused') return null
  const reason = result.reason
  if (command === SUBMIT && isJobRefusal(reason)) {
    return i18n.t(`jobs.refusal.${reason}`)
  }
  if (command.startsWith('rss.') && isRssRefusal(reason)) return i18n.t(`rss.refusal.${reason}`)
  return null
}

/** 一列的結果。認不得的拒絕理由印原文。 */
function RowResult({ result, command }: { result: ProposalRow; command: string }) {
  const { t } = useTranslation()
  const done = result.outcome === 'done'
  const reason = result.reason
  const said = refusalSentence(command, result) ?? (result.detail || reason)
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 text-xs">
      <span className={`label ${done ? 'text-ink' : 'text-ink-dim'}`}>
        {t(`agent.card.outcome.${result.outcome}`)}
      </span>
      {!done && result.outcome !== 'skipped' && said ? (
        <span className="min-w-0 text-ink">{said}</span>
      ) : null}
    </p>
  )
}

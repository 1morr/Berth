import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isJobRefusal } from '../api/jobs'
import { mediaQueryOptions } from '../api/media'
import { routesQueryOptions } from '../api/routes'
import { feedsQueryOptions, isRssRefusal, type PrimeMode } from '../api/rss'
import {
  decideProposal,
  proposalRefusalOf,
  proposalsKey,
  WAITING,
  type Proposal,
  type ProposalRow,
  type RouteAsk,
  type RouteOption,
  type SubgroupAsk,
  type SubgroupOption,
  type HeldEpisode,
  type SubscriptionRef,
} from '../api/proposals'
import { Checkbox, CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import i18n from '../i18n'
import { formatList } from '../i18n/list'
import { formatSize } from '../media/searchResult'
import { FirstRoundChoice, Options, SubgroupLine } from '../media/SubscribePanel'
import { ReleaseTitles } from '../rss/ReleaseTitles'
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
 * **作品放得進的 Route 不只一條時，Route 由人選**（票 23b）：清單是伺服器提出時存的
 * （`preview.routes`），預選這部作品上次用的那一條、沒用過就不預選；勾著的列沒選齊之前確認鍵不畫
 * （DESIGN.md「先選再確認」），伺服器也只收清單裡的。**一部作品只問一次**（M5.6 票 03）：卡片上的列
 * 依 `media_id` 分組，一組一個選擇，套到那組勾著的每一列；兩部以上作品、可選的 Route 有交集時，
 * 最上面多一個「全部套用」，之後仍可逐組改。
 *
 * **訂閱的字幕組由人選**（票 26）：選項是伺服器提出時讀番組頁或那一次搜尋存的（`preview.subgroups`），
 * 預選助理建議的那一個；`required` 的列沒選之前確認鍵同樣不畫。關鍵字訂閱列出選的那一組的第一批。
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
  // 一部作品只問一次：同一部作品的列共用一個選擇（M5.6 票 03）。
  const routeGroups = groupRoutes(rows, asks)
  const groupOf = new Map<number, RouteGroup>(
    routeGroups.flatMap((group) => group.rows.map((index): [number, RouteGroup] => [index, group])),
  )
  const [picks, setPicks] = useState<ReadonlyMap<string, number | null>>(
    () => new Map(routeGroups.map((group) => [group.mediaId, group.ask.preselected ?? null])),
  )
  const pickOf = (group: RouteGroup) => picks.get(group.mediaId) ?? null
  const routePick = (index: number) => {
    const group = groupOf.get(index)
    return group ? pickOf(group) : null
  }
  // 有勾著的列、而且作品放得進的 Route 不只一條的組：要人選。
  const routeUnpicked = routeGroups.filter(
    (group) => group.rows.some((index) => ticked.has(index)) && pickOf(group) === null,
  ).length
  const chooseRoute = (mediaId: string, route: number | null) =>
    setPicks((old) => new Map(old).set(mediaId, route))
  const applyRouteToAll = (route: number) =>
    setPicks(new Map(routeGroups.map((group) => [group.mediaId, route])))
  const groupAsks = proposal.preview.subgroups
  const [groupPicks, setGroupPicks] = useState<readonly (string | null)[]>(() =>
    rows.map((_, index) => groupAsks[index]?.preselected ?? null),
  )
  // 勾著、而且字幕組要人選的列。
  const choosingGroup = (index: number) => groupAsks[index]?.required === true && ticked.has(index)
  // 關鍵字訂閱的第一輪（票 26）：預設「下載這些並追之後的」。
  const roundOffers = proposal.preview.first_batch
  const [rounds, setRounds] = useState<readonly PrimeMode[]>(() => rows.map(() => 'all'))
  const groupsUnpicked = rows.filter(
    (_, index) => choosingGroup(index) && groupPicks[index] === null,
  ).length
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
        // Route 照舊逐列展開；沒勾的列不送，伺服器只要勾著的那幾列選齊。
        ...(approve && asking
          ? { routes: rows.map((_, index) => (ticked.has(index) ? routePick(index) : null)) }
          : {}),
        ...(approve && roundOffers.some(Boolean)
          ? {
              first_batch: rows.map((_, index) =>
                roundOffers[index] && ticked.has(index) ? (rounds[index] ?? 'all') : null,
              ),
            }
          : {}),
        // 字幕組同理；不必選的列送預選的那一個（伺服器沒收到也是用它）。
        ...(approve && groupAsks.some((ask) => ask !== null)
          ? {
              subgroups: rows.map((_, index) =>
                groupAsks[index] != null && ticked.has(index) ? groupPicks[index] : null,
              ),
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
      {waiting && asking ? (
        <>
          <p className="text-xs text-ink">{t('agent.card.routeLead')}</p>
          <RouteChoices
            groups={routeGroups}
            picks={picks}
            disabled={decide.isPending}
            onPick={chooseRoute}
            onPickAll={applyRouteToAll}
          />
        </>
      ) : null}
      {waiting && groupAsks.some((ask) => ask?.required) ? (
        <p className="text-xs text-ink">{t('agent.card.subgroupLead')}</p>
      ) : null}
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
                // 等人按的時候是這一頁上那部作品的選擇，按過之後是伺服器記下的那一條。
                pick: waiting ? routePick(index) : (proposal.routes?.[index] ?? null),
                single: proposal.preview.single_routes?.[index] ?? null,
              }}
              subgroup={{
                ask: groupAsks[index] ?? null,
                // 按過之後是伺服器記下的那一個；沒記（不必選的列）就是預選的那一個。
                pick: waiting
                  ? (groupPicks[index] ?? null)
                  : (proposal.subgroups?.[index] ?? groupAsks[index]?.preselected ?? null),
                editable: waiting && !decide.isPending,
                onPick: (key) =>
                  setGroupPicks((old) => old.map((value, at) => (at === index ? key : value))),
              }}
              existing={proposal.preview.existing[index] ?? []}
              held={proposal.preview.held[index] ?? []}
              round={{
                offered: roundOffers[index] === true,
                // 按過之後是伺服器記下的那一個；沒記是預設的那一個。
                pick: waiting ? (rounds[index] ?? 'all') : (proposal.first_batch?.[index] ?? 'all'),
                editable: waiting && !decide.isPending,
                onPick: (mode) =>
                  setRounds((old) => old.map((value, at) => (at === index ? mode : value))),
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
            {ticked.size > 0 && routeUnpicked === 0 && groupsUnpicked === 0 ? (
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
                  : routeUnpicked > 0
                    ? t('agent.card.routeMissing', { count: routeUnpicked })
                    : t('agent.card.subgroupMissing', { count: groupsUnpicked })}
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
  'rss.subscribe': 'agent.card.commands.rss_subscribe',
  'rss.subscribe_mikan': 'agent.card.commands.rss_subscribe_mikan',
  'rss.subscribe_search': 'agent.card.commands.rss_subscribe_search',
  'rss.add_feed': 'agent.card.commands.rss_add_feed',
  'rss.delete_feed': 'agent.card.commands.rss_delete_feed',
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
  subgroup,
  existing,
  held,
  round,
}: {
  command: string
  row: Row
  labelled: boolean
  external: readonly string[]
  /** 這一列按下去會送出幾個 torrent；`null` 是要送出時才知道，`undefined` 是不送。 */
  torrents: number | null | undefined
  route: RouteSlot
  subgroup: SubgroupSlot
  /** 這部作品提出時已經有的訂閱（票 26）。 */
  existing: readonly SubscriptionRef[]
  /** 這個發佈蓋到的集裡作品已經有的（帳本或 Jellyfin，票 28）。 */
  held: readonly HeldEpisode[]
  round: RoundSlot
}) {
  const { t } = useTranslation()
  // `labelled`：勾選框的標籤已經是發佈名，欄位裡不再印一次。
  if (isSubmit(command, row)) {
    return (
      <div className="grid gap-1">
        <SubmitRowBody row={row} labelled={labelled} route={route} />
        <Held episodes={held} />
      </div>
    )
  }
  if (command === 'rss.add_feed') {
    return (
      <div className="grid gap-2">
        <FeedRowBody row={row} external={external} />
        <Existing found={existing} />
      </div>
    )
  }
  if (command === 'rss.delete_feed') return <DeleteFeedRowBody row={row} />
  if (command === 'rss.subscribe') {
    // 票 09 之前存的卡選項沒有 `kind`：那時每一組都是 Mikan 的。
    const picked = subgroup.ask?.options.find((option) => option.key === subgroup.pick) ?? null
    const keyword = picked?.kind === 'nyaa' || picked?.kind === 'acgrip'
    return (
      <SubscribeRowBody
        look={{
          siteField: 'source',
          siteLabel: t('agent.card.fields.source'),
          site: picked?.kind ? sourceLabel(picked.kind) : t('agent.card.subgroupNone'),
          term: keyword ? (picked?.term ?? '') : '',
          name: text(row.subgroup),
          keyword,
          pickPrompt: t('agent.card.firstBatchPick'),
          showKind: true,
        }}
        row={row}
        external={external}
        torrents={torrents}
        route={route}
        subgroup={subgroup}
        existing={existing}
        round={round}
      />
    )
  }
  if (command === 'rss.subscribe_mikan' || command === 'rss.subscribe_search') {
    const mikan = command === 'rss.subscribe_mikan'
    // 沒有選項時照助理給的那一個訂（Mikan 是番組頁上的名字，關鍵字是發佈名上的組名）。
    const named = mikan
      ? text(row.subgroup_name) === '—'
        ? `#${String(row.subgroup_id)}`
        : text(row.subgroup_name)
      : text(row.subgroup)
    return (
      <SubscribeRowBody
        look={
          mikan
            ? {
                siteField: 'name',
                siteLabel: t('agent.card.fields.bangumi'),
                site: text(row.name) === '—' ? `#${String(row.bangumi_id)}` : text(row.name),
                term: '',
                name: named,
                keyword: false,
                pickPrompt: mikanSends(subgroup.ask, null, torrents),
                showKind: false,
              }
            : {
                siteField: 'kind',
                siteLabel: t('agent.card.fields.site'),
                site: text(row.kind),
                term: text(row.term),
                name: named,
                keyword: true,
                pickPrompt: t('agent.card.firstBatch', { count: 0 }),
                showKind: false,
              }
        }
        row={row}
        external={external}
        torrents={torrents}
        route={route}
        subgroup={subgroup}
        existing={existing}
        round={round}
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

/** 一列的 Route 那一格（票 23b）：`ask` 不是 `null` 時，值是卡片上面那部作品選的那一條。 */
interface RouteSlot {
  ask: RouteAsk | null
  /** 選了哪一條；`null` 是還沒選（或沒得選）。 */
  pick: number | null
  /** 只有一條放得進時伺服器提出那一刻記下的那一條（M5.6 票 04）：名字照預覽，不照參數。 */
  single: RouteOption | null
}

/** 卡片上一部作品的一組列（M5.6 票 03）：同一部作品的 Route 只問一次。 */
interface RouteGroup {
  mediaId: string
  rows: number[]
  ask: RouteAsk
}

/** 列的 `media_id`；沒有的是 `null`（Route 的清單由伺服器照它算，所以有 `ask` 的列一定有）。 */
function mediaIdOf(row: Row): string | null {
  return typeof row.media_id === 'string' ? row.media_id : null
}

function groupRoutes(rows: readonly Row[], asks: readonly (RouteAsk | null)[]): RouteGroup[] {
  const groups = new Map<string, RouteGroup>()
  rows.forEach((row, index) => {
    const ask = asks[index]
    const mediaId = mediaIdOf(row)
    if (ask === null || ask === undefined || mediaId === null) return
    const found = groups.get(mediaId)
    if (found) found.rows.push(index)
    else groups.set(mediaId, { mediaId, rows: [index], ask })
  })
  return [...groups.values()]
}

/** 一列訂閱的字幕組（票 26）：`ask` 不是 `null` 時有選項；`required` 時由人選。 */
interface SubgroupSlot {
  ask: SubgroupAsk | null
  /** 選了哪一個（選項的 `key`）；`null` 是還沒選。 */
  pick: string | null
  editable: boolean
  onPick: (key: string) => void
}

/** 一列關鍵字訂閱的第一輪（票 26）：`offered` 時卡上選「下載這些並追之後的」或「只追之後的」。 */
interface RoundSlot {
  offered: boolean
  pick: PrimeMode
  editable: boolean
  onPick: (mode: PrimeMode) => void
}

/**
 * Route 的值：要人選的作品是卡片上面選的那一條，按過之後是伺服器記下的那一條；只有一條可選的
 * 列是提出時記在預覽裡的那一條（M5.6 票 04），舊的卡才照 `fallback`。
 */
function RouteName({ route, fallback }: { route: RouteSlot; fallback: string }) {
  const { ask, pick, single } = route
  if (ask !== null) return ask.options.find((option) => option.id === pick)?.name ?? '—'
  return single?.name ?? fallback
}

/**
 * 卡片上面的 Route 選擇（M5.6 票 03）：一部作品一個選擇，套到它勾著的每一列；兩部以上作品、
 * 可選的 Route 有交集時，最上面一個「全部套用」一次填滿，之後仍可逐組改。
 */
function RouteChoices({
  groups,
  picks,
  disabled,
  onPick,
  onPickAll,
}: {
  groups: readonly RouteGroup[]
  picks: ReadonlyMap<string, number | null>
  disabled: boolean
  onPick: (mediaId: string, route: number | null) => void
  onPickAll: (route: number) => void
}) {
  const { t } = useTranslation()
  if (groups.length === 0) return null
  const pickOf = (group: RouteGroup) => picks.get(group.mediaId) ?? null
  const shared = groups.length > 1 ? sharedRoutes(groups) : []
  const first = pickOf(groups[0])
  // 每一組選的都一樣時，全部套用照那個值畫；有人改過就回到沒選。
  const sharedPick = groups.every((group) => pickOf(group) === first) ? first : null
  return (
    <div className="grid gap-2">
      {shared.length > 0 ? (
        <RouteSelect
          label={t('agent.card.routeApplyAll')}
          placeholder={t('agent.card.routeApplyAllChoose')}
          // 全部套用是一個動作：沒選時顯示的那一項不是一個選得下去的狀態。
          placeholderDisabled
          required={false}
          options={shared}
          pick={sharedPick}
          disabled={disabled}
          onPick={(route) => {
            if (route !== null) onPickAll(route)
          }}
        />
      ) : null}
      {groups.map((group) => (
        <WorkRoute
          key={group.mediaId}
          group={group}
          many={groups.length > 1}
          pick={pickOf(group)}
          disabled={disabled}
          onPick={(route) => onPick(group.mediaId, route)}
        />
      ))}
    </div>
  )
}

/** 一組（一部作品）的 Route：兩部以上作品時標出是哪一部。 */
function WorkRoute({
  group,
  many,
  pick,
  disabled,
  onPick,
}: {
  group: RouteGroup
  many: boolean
  pick: number | null
  disabled: boolean
  onPick: (route: number | null) => void
}) {
  const { t } = useTranslation()
  const media = useQuery(mediaQueryOptions(group.mediaId))
  // 作品名還沒讀到（或讀不到）時只寫 Route：作品 id 是機器字串，不放進 `.label`。
  const title = media.data?.title
  return (
    <RouteSelect
      label={
        many && title ? t('agent.card.routeForWork', { work: title }) : t('agent.card.fields.route')
      }
      placeholder={t('agent.card.routeChoose')}
      options={group.ask.options}
      pick={pick}
      disabled={disabled}
      onPick={onPick}
    />
  )
}

function RouteSelect({
  label,
  placeholder,
  placeholderDisabled = false,
  required = true,
  options,
  pick,
  disabled,
  onPick,
}: {
  label: string
  placeholder: string
  placeholderDisabled?: boolean
  /** 一組的 Route 是必選的；「全部套用」只是捷徑。 */
  required?: boolean
  options: RouteAsk['options']
  pick: number | null
  disabled: boolean
  onPick: (route: number | null) => void
}) {
  const id = useId()
  return (
    <div className="grid gap-0.5">
      <label htmlFor={id} className="label text-ink-dim">
        {label}
      </label>
      <select
        id={id}
        required={required}
        disabled={disabled}
        value={pick ?? ''}
        onChange={(event) => onPick(event.target.value === '' ? null : Number(event.target.value))}
        className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
      >
        <option value="" disabled={placeholderDisabled}>
          {placeholder}
        </option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </div>
  )
}

/** 每一組都有的 Route：全部套用只列這些。 */
function sharedRoutes(groups: readonly RouteGroup[]): RouteAsk['options'] {
  const [first, ...rest] = groups
  return first.ask.options.filter((option) =>
    rest.every((group) => group.ask.options.some((other) => other.id === option.id)),
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

/**
 * 一列訂閱（M5 票 26、M5.6 票 09）：來源那一格、字幕組、作品、Route 與送出量；關鍵字那一條另有
 * 搜尋詞、第一批與第一輪。兩種來源的卡片共用這一份畫法，差別只在呼叫端算出來的 `look`。
 */
function SubscribeRowBody({
  look,
  row,
  external,
  torrents,
  route,
  subgroup,
  existing,
  round,
}: {
  /** 這一列怎麼訂：來源那一格的欄位名、標籤與值，搜尋詞，字幕組名，是不是關鍵字那一條。 */
  look: {
    siteField: string
    siteLabel: string
    site: ReactNode
    term: string
    name: string
    keyword: boolean
    /** 有選項、還沒選時「送出」那一格寫什麼（每種卡本來就寫得不一樣）。 */
    pickPrompt: string
    /** 選項上標不標來源（只有以作品訂閱的卡有兩條路）。 */
    showKind: boolean
  }
  row: Row
  external: readonly string[]
  torrents: number | null | undefined
  route: RouteSlot
  subgroup: SubgroupSlot
  /** 這部作品提出時已經有的訂閱（票 26）。 */
  existing: readonly SubscriptionRef[]
  round: RoundSlot
}) {
  const { t } = useTranslation()
  const mediaId = mediaIdOf(row) ?? ''
  const media = useQuery({ ...mediaQueryOptions(mediaId), enabled: mediaId !== '' })
  const given = media.data?.routes.find((choice) => choice.id === row.route_id)
  const { ask } = subgroup
  const picked = ask?.options.find((option) => option.key === subgroup.pick) ?? null
  const choosing = ask !== null && subgroup.editable && (ask.required || ask.options.length > 1)
  // 沒有選項（番組頁或搜尋上沒有字幕組）：照助理給的那一個訂。
  const sends =
    picked === null
      ? ask === null
        ? look.keyword
          ? t('agent.card.firstBatch', { count: 0 })
          : mikanSends(ask, null, torrents)
        : look.pickPrompt
      : look.keyword
        ? round.pick === 'later'
          ? t('agent.card.firstBatchLater')
          : t('agent.card.firstBatch', { count: picked.titles.length })
        : mikanSends(ask, picked, torrents)
  return (
    <div className="grid gap-2">
      <Fields
        external={external}
        fields={[
          { name: look.siteField, label: look.siteLabel, value: look.site },
          ...(look.term
            ? [
                {
                  name: 'term',
                  label: t('agent.card.fields.term'),
                  value: look.term,
                  mono: true,
                },
              ]
            : []),
          {
            name: 'subgroup',
            label: t('agent.card.fields.subgroup'),
            value: ask === null ? look.name : (picked?.name ?? t('agent.card.subgroupNone')),
          },
          {
            name: 'media_id',
            label: t('agent.card.fields.media'),
            value: media.data?.title ?? mediaId,
          },
          {
            name: 'route_id',
            label: t('agent.card.fields.route'),
            value: <RouteName route={route} fallback={given?.name ?? `#${String(row.route_id)}`} />,
          },
          { name: 'sends', label: t('agent.card.fields.sends'), value: sends },
        ]}
      />
      {choosing ? (
        <Options
          label={t('agent.card.subgroupChoose')}
          items={ask.options}
          keyOf={(option) => option.key}
          picked={picked}
          onPick={(option) => subgroup.onPick(option.key)}
          render={(option) => (
            <SubgroupLine
              group={option}
              source={look.showKind ? sourceLabel(option.kind) : undefined}
            />
          )}
        />
      ) : null}
      {look.keyword ? (
        <FirstBatch option={picked} missing={ask === null} later={round.pick === 'later'} />
      ) : null}
      {look.keyword && round.offered ? (
        round.editable ? (
          <FirstRoundChoice value={round.pick} onChange={round.onPick} />
        ) : (
          <p className="text-xs text-ink">{t(`rss.subscribe.round.${round.pick}`)}</p>
        )
      ) : null}
      <Existing found={existing} />
    </div>
  )
}

/** 來源的名字（M5.6 票 09）：站名走 i18n，與 RSS 頁那幾顆同一個字。 */
function sourceLabel(kind: SubgroupOption['kind']): string {
  if (kind === 'mikan' || kind === 'nyaa' || kind === 'acgrip') {
    return i18n.t(`rss.kind.${kind}`)
  }
  return ''
}

/** 訂閱 Mikan 按下去就當場送整季，不經第一批確認（協調者 2026-10-27）：按的人要知道送多少。 */
function mikanSends(
  ask: SubgroupAsk | null,
  picked: SubgroupOption | null,
  torrents: number | null | undefined,
): string {
  if (picked !== null) return i18n.t('agent.card.wholeSeason', { count: picked.releases })
  if (ask !== null) return i18n.t('agent.card.wholeSeasonPick')
  return typeof torrents === 'number'
    ? i18n.t('agent.card.wholeSeason', { count: torrents })
    : i18n.t('agent.card.wholeSeasonUnknown')
}

/** 關鍵字訂閱的第一批（票 26）：選的那一組這一次搜到的發佈名，按下確認就送出。 */
function FirstBatch({
  option,
  missing,
  later,
}: {
  option: SubgroupOption | null
  missing: boolean
  later: boolean
}) {
  const { t } = useTranslation()
  if (missing) return <p className="text-xs text-ink-dim">{t('agent.card.firstBatchNone')}</p>
  if (option === null)
    return <p className="text-xs text-ink-dim">{t('agent.card.firstBatchPick')}</p>
  return (
    <div className="grid gap-1 text-xs">
      <p className="label text-ink-dim">{t('agent.card.fields.firstBatch')}</p>
      <ReleaseTitles titles={option.titles} />
      <p className="max-w-prose text-ink-dim">
        {later ? t('rss.subscribe.round.laterHint') : t('agent.card.firstBatchAfter')}
      </p>
    </div>
  )
}

/**
 * 這一列的發佈蓋到的集裡，作品已經有的（票 28，使用者 2026-10-30）：伺服器提出時算的（帳本或這個人的
 * Jellyfin），不靠模型說。照季分組、連續的集收成區間。
 */
function Held({ episodes }: { episodes: readonly HeldEpisode[] }) {
  const { t, i18n: i18nInstance } = useTranslation()
  if (episodes.length === 0) return null
  const language = i18nInstance.language
  const seasons = [...new Set(episodes.map((one) => one.season))].sort((a, b) => a - b)
  const parts = seasons.map((season) =>
    t('agent.card.heldSeason', {
      season,
      episodes: formatList(
        spans(episodes.filter((one) => one.season === season).map((one) => one.episode)),
        language,
      ),
    }),
  )
  return (
    <p className="label text-xs text-ink">
      {t('agent.card.held', { episodes: formatList(parts, language) })}
    </p>
  )
}

/** `[3, 4, 5, 7]` → `['3–5', '7']`。 */
function spans(numbers: readonly number[]): string[] {
  const ordered = [...new Set(numbers)].sort((a, b) => a - b)
  const found: string[] = []
  let start = ordered[0]
  let previous = start
  for (const number of [...ordered.slice(1), null]) {
    if (number !== null && number === previous + 1) {
      previous = number
      continue
    }
    found.push(start === previous ? `${start}` : `${start}–${previous}`)
    if (number !== null) start = previous = number
  }
  return found
}

/** 這部作品已經有的訂閱（票 26）：說出來，要不要再訂一份由人決定。 */
function Existing({ found }: { found: readonly SubscriptionRef[] }) {
  const { t } = useTranslation()
  if (found.length === 0) return null
  return (
    <div className="grid gap-0.5 border-2 border-rule-strong p-2 text-xs">
      <p className="text-ink">{t('agent.card.existingLead')}</p>
      <ul className="grid gap-0.5">
        {found.map((ref) => (
          <li key={`${ref.feed_id}:${ref.subgroup}`} className="text-ink">
            <span className="value wrap-anywhere">{ref.name}</span>
            <span className="text-ink-dim">
              {' · '}
              {ref.subgroup
                ? t('agent.card.existingSubgroup', { subgroup: ref.subgroup })
                : t('agent.card.existingEvery')}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 刪除訂閱（票 26）：哪一條 Feed、刪掉會怎樣。Feed 清單只有管理員讀得到，刪 Feed 也只有管理員。 */
function DeleteFeedRowBody({ row }: { row: Row }) {
  const { t } = useTranslation()
  const feeds = useQuery(feedsQueryOptions())
  const feed = feeds.data?.find((one) => one.id === row.feed_id)
  return (
    <div className="grid gap-1">
      <Fields
        external={[]}
        fields={[
          {
            name: 'feed_id',
            label: t('agent.card.fields.feed'),
            value: feed?.name ?? `#${String(row.feed_id)}`,
          },
          ...(feed ? [{ name: 'kind', label: t('agent.card.fields.site'), value: feed.kind }] : []),
        ]}
      />
      <p className="max-w-prose text-xs text-ink">
        {t('agent.card.deleteFeed', { count: feed?.items ?? 0 })}
      </p>
    </div>
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
        <RouteName route={route} fallback={given?.name ?? `#${row.route_id}`} />
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

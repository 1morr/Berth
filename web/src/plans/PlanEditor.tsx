import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import {
  editPlanItems,
  planQueryOptions,
  type Plan,
  type PlanAction,
  type PlanItem,
} from '../api/plans'
import { CollapsibleRow } from '../components/CollapsibleRow'
import { Checkbox, COMPACT_BUTTON, Field, GhostButton, Notice } from '../components/controls'
import { Dot } from '../components/Dot'
import { formatCoverage, formatEpisode } from '../components/episodes'
import { groupRows } from '../components/rowGroups'
import type { Said } from '../review/useConfirmAudits'
import { seriesCorrectedText } from '../rss/seriesValues'
import { planRefusalText } from './planRefusal'
import { Reasons } from './Reasons'

/**
 * 一份停在 review 的 Plan，逐列可改（M2 票 07、`.scratch/m2/plan-edit-shape.md`）。
 *
 * **要人看的列攤在最前**：待審核、對不到、有錯誤的、改過的。一包 39 個檔案裡說不清楚的通常只有一到五列，
 * 其餘照 `/jobs` 的分組收著（處置 × 季 × 信心），展開一樣逐列改得動。
 *
 * **每一列的目標路徑是後端給的**（plan §5：命名是純函式）：待審核那幾列是「核准的話」會落在哪裡，
 * 改完一列的回應就帶著新的路徑——前端不重算任何一條。改得成哪幾種處置也是後端給的（依檔案分類）。
 *
 * **RSS Series 送的計劃，指派到某一集時多一格「套用到這個 RSS Series」**（M3 票 14b），與 audit 列上的那一格
 * 同一個元件與文案（`RematchForm`）：連載中的 split-cour 第一批整批停在這裡，改一列就要全修好。
 */
export function PlanEditor({
  plan,
  hash,
  onUnapplied,
  onSeries,
}: {
  plan: Plan
  hash: string
  /** 某一列的表單改了還沒套用（或不再是）。核准要先擋住它（`PlanRow`）；**要是穩定的函式**，表單靠它回報。 */
  onUnapplied: Unapplied
  /** 套用到 RSS Series 之後那一句：其餘的計劃跟著動了、從佇列上消失，結果要看得見（`Said` 的 `shown`）。 */
  onSeries: (said: string) => void
}) {
  const { t } = useTranslation()
  // 套用成功時那一列收回、畫面上變的是一條路徑——看不見畫面的人要另外聽到。
  const [said, setSaid] = useState('')
  // 一般的套用只念給看不見畫面的人；套用到 Series 那一句要看得見（`shown`），交給 `PlanRow` 畫在頁上。
  const applied = useCallback<Said>(
    (text, shown = false) => (shown ? onSeries(text) : setSaid(text)),
    [onSeries],
  )
  const held = plan.items.filter(needsYou)
  const rest = plan.items.filter((item) => !needsYou(item))

  return (
    <div className="grid min-w-0 gap-3">
      <p aria-live="polite" className="sr-only">
        {said}
      </p>
      {held.length > 0 && (
        <div className="grid min-w-0 gap-2">
          <p className="label text-ink">{t('review.plan.held', { count: held.length })}</p>
          <ol className="grid min-w-0 gap-3">
            {held.map((item) => (
              <EditableItem
                key={item.id}
                item={item}
                plan={plan}
                hash={hash}
                heavy
                onApplied={applied}
                onUnapplied={onUnapplied}
              />
            ))}
          </ol>
        </div>
      )}
      {rest.length > 0 && (
        <div className="grid min-w-0 gap-2">
          <p className="label text-ink-dim">{t('review.plan.rest', { count: rest.length })}</p>
          <div className="grid gap-px bg-rule">
            {byDecision(rest).map((group) => {
              const [first] = group.rows
              const action = t(`jobs.plan.action.${first.action}`)
              const coverage = formatCoverage(first.season, group.rows)
              return (
                <CollapsibleRow
                  key={group.key}
                  name={[action, coverage].filter(Boolean).join(' ')}
                  summary={
                    <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="label bg-deck px-1.5 py-0.5 text-ink">{action}</span>
                      <span className="label text-ink-dim">
                        {t(`jobs.plan.confidence.${first.confidence}`)}
                      </span>
                      {coverage && (
                        <>
                          <Dot />
                          <span className="value text-sm text-ink">{coverage}</span>
                        </>
                      )}
                      <Dot />
                      <span className="value text-xs text-ink-dim">
                        {t('jobs.plan.files', { count: group.rows.length })}
                      </span>
                    </span>
                  }
                >
                  {() => (
                    <ol className="grid min-w-0 gap-3 px-4 py-3">
                      {group.rows.map((item) => (
                        <EditableItem
                          key={item.id}
                          item={item}
                          plan={plan}
                          hash={hash}
                          onApplied={applied}
                          onUnapplied={onUnapplied}
                        />
                      ))}
                    </ol>
                  )}
                </CollapsibleRow>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/** 一列的表單「改了還沒套用」的狀態變了：`dirty` 是 false 時那一列不再算。 */
export type Unapplied = (item: PlanItem, dirty: boolean) => void

/** 要人看的那幾列：還沒決定的、對不到的、出過錯的，以及人改過的（改完不該跳走、讓人找不到剛改的那一列）。 */
function needsYou(item: PlanItem): boolean {
  if (item.applied) return false
  return (
    item.action === 'review' ||
    item.action === 'unmatched' ||
    item.error !== '' ||
    item.reasons.some((reason) => reason.code === 'set_by_user')
  )
}

function byDecision(items: readonly PlanItem[]) {
  return groupRows(
    items,
    (item) => [item.action, item.season ?? '', item.confidence].join(':'),
    () => false,
  )
}

/**
 * 一列：季集 · 檔名 ·「改」，下一行是處置與信心，再下一行是它會落在哪裡，最後是理由。
 *
 * 目標那一行是這一頁的重點（原則 2「動手前先給看」），所以它是 `.value` 的全路徑、不截斷；
 * 沒有路徑時說出**為什麼**沒有——不會進媒體庫，或還沒有季集要先改。
 */
function EditableItem({
  item,
  plan,
  hash,
  heavy = false,
  onApplied,
  onUnapplied,
}: {
  item: PlanItem
  plan: Plan
  hash: string
  heavy?: boolean
  onApplied: Said
  onUnapplied: Unapplied
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const returning = useRef(false)
  const episode = formatEpisode(item)

  // 表單收起之後焦點回到「改」（取消與套用成功都是）：否則它落在一個已經不在的元素上，回到頁首。
  useEffect(() => {
    if (!editing && returning.current) {
      returning.current = false
      trigger.current?.focus()
    }
  }, [editing])

  function close() {
    returning.current = true
    setEditing(false)
  }

  return (
    <li
      className={`grid min-w-0 gap-1.5 border-l-2 pl-3 ${heavy ? 'border-rule-strong' : 'border-rule'}`}
    >
      <div className="flex min-w-0 flex-wrap items-start gap-x-2 gap-y-1">
        <span className="value text-xs text-ink">{episode || '—'}</span>
        {/* 來源檔名整條換行，不截斷：它是使用者認得出這個檔案的東西。**不撐滿那一行**：撐滿的話「改」在桌機上
            離檔名一千多 px（M2 票 16 critique），看不出它改的是哪一列。 */}
        <span className="value min-w-0 text-xs wrap-anywhere text-ink">{item.rel_path}</span>
        {item.actions.length > 0 && !editing && (
          <button
            ref={trigger}
            type="button"
            className={COMPACT_BUTTON}
            aria-label={`${t('review.plan.edit')} ${item.rel_path}`}
            onClick={() => setEditing(true)}
          >
            {t('review.plan.edit')}
          </button>
        )}
      </div>

      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-1.5 py-0.5 text-ink">
          {t(`jobs.plan.action.${item.action}`)}
        </span>
        <span className="label text-ink-dim">{t(`jobs.plan.confidence.${item.confidence}`)}</span>
      </p>

      <Landing item={item} />
      {item.error && <p className="value text-xs wrap-anywhere text-ink-dim">{item.error}</p>}
      <Reasons reasons={item.reasons} />

      {editing && (
        <ItemForm
          item={item}
          plan={plan}
          hash={hash}
          onUnapplied={onUnapplied}
          onCancel={close}
          onApplied={(said, shown) => {
            close()
            onApplied(said, shown)
          }}
        />
      )}
    </li>
  )
}

/** 它會落在哪裡，或為什麼不會。 */
function Landing({ item }: { item: PlanItem }) {
  const { t } = useTranslation()

  if (item.target_path) {
    return (
      <p className="grid min-w-0 gap-0.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-2">
        <span className="label text-ink-dim">
          {item.applied ? t('review.plan.landed') : t('review.plan.lands')}
        </span>
        <span className="value min-w-0 text-xs wrap-anywhere text-ink">{item.target_path}</span>
      </p>
    )
  }
  // 待審核而沒有路徑：沒有提案，這一列會擋住核准——說出下一步（原則 4），字用 ink 不用弱字。
  if (item.action === 'review') {
    return <p className="text-xs text-ink">{t('review.plan.noProposal')}</p>
  }
  return <p className="text-xs text-ink-dim">{t('review.plan.nowhere')}</p>
}

/**
 * 改一列：處置、季、起集、迄集。「套用」立刻存（`PUT /plans/{id}/items`），回應就是改完的整份，
 * 直接寫進快取——那一列（與跟著搬的字幕）當場換成新的路徑。
 *
 * 季集只屬於劇集的入庫：選了別的處置、或這是電影，那三格不畫（後端也拒絕帶著它們的改動）。
 *
 * 「套用到這個 RSS Series」預設勾選（同 `RematchForm`：一集錯多半整批一起錯）。勾著時同一支多帶
 * `apply_to_series`：其餘停在審核的計劃跟著重新規劃、多半就此入庫，所以佇列、下載列表與作品頁都要重問。
 */
function ItemForm({
  item,
  plan,
  hash,
  onUnapplied,
  onCancel,
  onApplied,
}: {
  item: PlanItem
  plan: Plan
  hash: string
  onUnapplied: Unapplied
  onCancel: () => void
  onApplied: Said
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const selectId = useId()
  const refusalId = useId()
  // 打開那一刻的值。與它不同才算「改了」：只是打開看一眼不擋核准。
  const [opened] = useState(() => ({
    action: initialAction(item),
    season: numberText(item.season),
    start: numberText(item.episode_start),
    end: numberText(item.episode_end),
  }))
  const [action, setAction] = useState<PlanAction>(opened.action)
  const [season, setSeason] = useState(opened.season)
  const [start, setStart] = useState(opened.start)
  const [end, setEnd] = useState(opened.end)
  const [toSeries, setToSeries] = useState(true)
  const numbered = action === 'import' && plan.media_kind === 'tv'
  // 套用到 Series 要的是季集：只有指派到某一集才有（後端對其餘處置回 `action_not_allowed`）。
  const applying = plan.series !== null && numbered && toSeries
  const dirty =
    action !== opened.action ||
    season !== opened.season ||
    start !== opened.start ||
    end !== opened.end

  // 核准不帶表單上的值（`approve` 核准的是已經存下來的那一份），所以改到一半的列要讓 `PlanRow` 擋住核准（M3 票 06）。
  useEffect(() => onUnapplied(item, dirty), [item, dirty, onUnapplied])
  // 收起（取消、套用成功、整組收合）之後這一列不再算。
  useEffect(() => () => onUnapplied(item, false), [item, onUnapplied])

  const apply = useMutation({
    mutationFn: () =>
      editPlanItems(
        plan.id,
        [
          {
            id: item.id,
            action,
            season: numbered ? numberOf(season) : null,
            episode_start: numbered ? numberOf(start) : null,
            episode_end: numbered ? numberOf(end) : null,
          },
        ],
        applying,
      ),
    onSuccess: ({ corrected, ...updated }) => {
      queryClient.setQueryData(planQueryOptions(hash, plan.id).queryKey, updated)
      // 佇列那一列的計數（要入庫幾個、低信心幾個）跟著變了。
      void queryClient.invalidateQueries({ queryKey: ['review'] })
      if (!corrected) return onApplied(t('review.plan.applied'))
      // 其餘的計劃重新規劃、入庫了：它們的下載與作品頁的入庫狀態都變了。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      void queryClient.invalidateQueries({ queryKey: ['media'] })
      onApplied(`${seriesCorrectedText(t, corrected)} ${t('review.plan.stillToApprove')}`, true)
    },
  })
  const refused = apply.isError ? planRefusalText(t, apply.error) : null

  function submit(event: FormEvent) {
    event.preventDefault()
    apply.mutate()
  }

  return (
    <form
      onSubmit={submit}
      aria-describedby={refused ? refusalId : undefined}
      className="grid min-w-0 gap-3 border-2 border-rule bg-hull px-3 py-3"
    >
      <div className="grid grid-cols-2 items-start gap-3 sm:grid-cols-4">
        <p className="col-span-2 grid gap-2 sm:col-span-1">
          <label htmlFor={selectId} className="label text-ink-dim">
            {t('review.plan.field.action')}
          </label>
          {/* 表單是按「改」打開的：焦點跟著進來，否則它留在一顆已經不在的按鈕上（M2 票 16 audit P2）。 */}
          <select
            id={selectId}
            autoFocus
            value={action}
            onChange={(event) => setAction(event.target.value as PlanAction)}
            className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
          >
            {item.actions.map((choice) => (
              <option key={choice} value={choice}>
                {t(`jobs.plan.action.${choice}`)}
              </option>
            ))}
          </select>
        </p>
        {numbered && (
          <>
            <Field
              label={t('review.plan.field.season')}
              type="number"
              inputMode="numeric"
              min={0}
              required
              value={season}
              onChange={(event) => setSeason(event.target.value)}
            />
            <Field
              label={t('review.plan.field.start')}
              type="number"
              inputMode="numeric"
              min={0}
              required
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
            <Field
              label={t('review.plan.field.end')}
              hint={t('review.plan.endHint')}
              type="number"
              inputMode="numeric"
              min={0}
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </>
        )}
      </div>

      {plan.series !== null && numbered && (
        <Checkbox
          label={t('rematch.applyToSeries')}
          hint={t('rematch.applyToSeriesHint')}
          checked={toSeries}
          onChange={setToSeries}
        />
      )}

      {refused !== null && (
        <div id={refusalId}>
          <Notice signal="blocked" label={t('common.failed')}>
            {refused}
          </Notice>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <GhostButton type="submit" busy={apply.isPending}>
          {apply.isPending ? t('review.plan.working') : t('review.plan.apply')}
        </GhostButton>
        <GhostButton type="button" onClick={onCancel}>
          {t('review.plan.cancel')}
        </GhostButton>
      </div>
    </form>
  )
}

/** 表單一打開的處置：待審核的列多半就是要照提案入庫，所以預選「入庫」（它改得成的話）。 */
function initialAction(item: PlanItem): PlanAction {
  if (item.actions.includes(item.action)) return item.action
  if (item.action === 'review' && item.actions.includes('import')) return 'import'
  return item.actions[0] ?? item.action
}

function numberText(value: number | null): string {
  return value === null ? '' : String(value)
}

function numberOf(text: string): number | null {
  return text.trim() === '' ? null : Number(text)
}

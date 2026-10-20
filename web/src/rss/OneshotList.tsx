import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { refusalOf, submitJob } from '../api/jobs'
import type { Media } from '../api/media'
import { ONESHOT_KEY, type Oneshot, type OneshotItem } from '../api/rss'
import { GhostButton, PrimaryButton, STICKY_ACTION } from '../components/controls'
import { Dot } from '../components/Dot'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { whenText } from '../components/queueText'
import { JobLink } from '../jobs/JobLink'
import { estimate, formatSize, tagTokens } from '../media/searchResult'
import { freshSingles, sendOrder, tally, type Outcome } from './oneshotBatch'

/**
 * 一次性連結讀到的清單：勾選、「勾選全部單集」、逐筆送出與每一列的結果（M3 票 18；M4 票 112 抽出來，
 * /rss 的一次性連結與作品頁的「只下載現有的」共用）。
 *
 * **不建 Feed**：送是逐筆的一般送單 `POST /jobs`（`trigger = manual`，與搜尋結果表同一支）。一次勾的
 * 同一批共用一部作品與一條 Route。資料夾名在第一次送單那一刻定下來，所以它印在送出鍵的上方
 * （同 `SubmitAction`）。
 *
 * **排除條件不擋**（它們只管自動下載）：合集、區間標出來，照樣勾得了；「勾選全部單集」不勾它們。
 *
 * 送出是**逐筆、舊的先**：一筆被拒不擋下一筆（那一列就地說理由）；不是「後端說不行」的失敗（網路斷了、
 * 401）就停下來，沒送的留著勾。送完清單不會消失，結果那一句是清單裡的 `role="status"`，不經頁面的
 * `aria-live`（那一條給會離開畫面的列）。
 *
 * 換一條網址就是另一批：呼叫端以網址當 `key`，勾選與結果從頭來。
 */
export function OneshotList({
  read,
  media,
  route,
  picker,
}: {
  read: Oneshot
  media: Media | undefined
  route: number | null
  /**
   * 清單上方挑作品與 Route 的那一塊（/rss 的一次性連結）；`locked` 是送出中。作品頁已經知道作品、
   * Route 在訂閱那裡選，不給。
   */
  picker?: (locked: boolean) => ReactNode
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const listId = useId()
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set())
  const [outcomes, setOutcomes] = useState<ReadonlyMap<string, Outcome>>(new Map())
  const [progress, setProgress] = useState(0)
  const items = read.items
  const all = freshSingles(items)
  const allPicked = all.size > 0 && [...all].every((guid) => picked.has(guid))

  const send = useMutation({
    mutationFn: async () => {
      if (!media || route === null) throw new Error('nothing picked')
      const order = sendOrder(items, picked)
      // 這一批的結果另外記一份：`onSuccess` 裡讀 state 拿到的是按下那一刻的。
      const settled = new Map<string, Outcome>()
      setProgress(0)
      for (const row of order) {
        let outcome: Outcome
        try {
          const created = await submitJob({
            // 與搜尋結果同一條路（M4 票 79）：送記下的那一筆的 id，不送網址。
            source_id: row.source_id,
            media: media.id,
            route,
          })
          outcome = { kind: created.created ? 'sent' : 'already', hash: created.job.hash }
        } catch (error) {
          const refused = refusalOf(error)
          // 不是後端說不行（網路斷了、登入過期）：停下來，沒送的留著勾。
          if (refused === null) throw error
          outcome = { kind: 'refused', reason: refused.reason, detail: refused.detail }
        }
        settled.set(row.guid, outcome)
        setOutcomes((before) => new Map(before).set(row.guid, outcome))
        if (outcome.kind !== 'refused') {
          setPicked((before) => {
            const next = new Set(before)
            next.delete(row.guid)
            return next
          })
        }
        setProgress((done) => done + 1)
      }
      return tally(settled)
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 送單之後這部作品變成 tracked、資料夾名也定了（同 `SubmitAction`）。
        queryClient.invalidateQueries({ queryKey: ['media'] }),
        // 重讀一次：哪幾筆已經有下載了。
        queryClient.invalidateQueries({ queryKey: ONESHOT_KEY }),
      ])
    },
  })

  const toggle = (guid: string, on: boolean) =>
    setPicked((before) => {
      const next = new Set(before)
      if (on) next.add(guid)
      else next.delete(guid)
      return next
    })

  if (items.length === 0) {
    return <p className="max-w-prose text-sm text-ink-dim">{t('rss.oneshot.empty')}</p>
  }

  const order = sendOrder(items, picked)
  return (
    <div className="grid gap-3">
      <p className="text-xs text-ink-dim">
        {t('rss.oneshot.count', { count: items.length })} <Dot />{' '}
        <span className="value">{t(`rss.kind.${read.kind}`)}</span>
      </p>

      {picker?.(send.isPending)}

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <p id={listId} className="label text-ink-dim">
          {t('rss.oneshot.list')}
        </p>
        {all.size > 0 && (
          <GhostButton
            type="button"
            disabled={send.isPending}
            onClick={() => setPicked(allPicked ? new Set() : all)}
          >
            {allPicked ? t('rss.oneshot.pickNone') : t('rss.oneshot.pickAll', { count: all.size })}
          </GhostButton>
        )}
      </div>
      <ul aria-labelledby={listId} className="grid gap-px bg-rule">
        {items.map((row) => (
          <li key={row.guid} className="min-w-0 bg-well px-4 py-2.5">
            <Row
              row={row}
              checked={picked.has(row.guid)}
              locked={send.isPending}
              outcome={outcomes.get(row.guid)}
              onToggle={(on) => toggle(row.guid, on)}
            />
          </li>
        ))}
      </ul>

      {send.isError && (
        <RequestFailed error={send.error} lead={t('rss.oneshot.stopped', { done: progress })} />
      )}
      {send.data && (
        <p role="status" className="text-sm text-ink">
          {t('rss.oneshot.done', send.data)}
        </p>
      )}

      <div className={STICKY_ACTION}>
        <div className="grid gap-2 sm:max-w-md">
          {media && route !== null ? (
            <>
              <p className="max-w-prose text-xs text-ink">
                {media.folder_frozen ? t('rss.bind.alreadyFrozen') : t('rss.oneshot.willFreeze')}
              </p>
              {/* 資料夾名是機器字串，會原樣出現在檔案系統上（同 `SubmitAction`）。 */}
              <p className="value text-xs wrap-anywhere text-ink">{media.folder_name || '—'}</p>
              <PrimaryButton
                type="button"
                busy={send.isPending}
                disabled={order.length === 0}
                onClick={() => send.mutate()}
              >
                {send.isPending
                  ? t('rss.oneshot.sending', { done: progress, total: order.length })
                  : order.length === 0
                    ? t('rss.oneshot.pickFirst')
                    : t('rss.oneshot.send', { count: order.length })}
              </PrimaryButton>
            </>
          ) : (
            <p className="max-w-prose text-xs text-ink-dim">{t('rss.oneshot.needWork')}</p>
          )}
        </div>
      </div>
    </div>
  )
}

/** 清單的一列：勾選格、發佈名，下面一行解析結果，再下面是「已經有了」與送出之後的結果。 */
function Row({
  row,
  checked,
  locked,
  outcome,
  onToggle,
}: {
  row: OneshotItem
  checked: boolean
  locked: boolean
  outcome: Outcome | undefined
  onToggle: (on: boolean) => void
}) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const factsId = `${id}-facts`
  const { code, noteKey } = estimate(row)
  const tokens = tagTokens(row.tags)
  const done = outcome !== undefined && outcome.kind !== 'refused'

  return (
    <div className="grid min-w-0 gap-1">
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          aria-describedby={factsId}
          checked={checked}
          disabled={locked || done}
          onChange={(event) => onToggle(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
        />
        <label htmlFor={id} className="value min-w-0 text-sm wrap-anywhere text-ink">
          {row.title}
        </label>
      </div>
      <p id={factsId} className="pl-7 text-xs text-ink-dim">
        {/* 合集、區間只標示、不擋（排除條件只管自動下載，brief §15）：中性色塊，不塗漆。 */}
        {row.release_kind !== 'single' && (
          <>
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.neutral}`}>
              {t(`rss.oneshot.kind.${row.release_kind}`)}
            </span>{' '}
          </>
        )}
        <span className="value">{[code, noteKey ? t(noteKey) : ''].filter(Boolean).join(' ')}</span>
        {tokens.length > 0 && (
          <>
            {' '}
            <Dot /> <span className="value">{tokens.join(' · ')}</span>
          </>
        )}
        {row.published_at && (
          <>
            {' '}
            <Dot /> {t('rss.items.published')}{' '}
            <span className="value">{whenText(row.published_at, i18n.language)}</span>
          </>
        )}
        {row.size !== null && (
          <>
            {' '}
            <Dot /> <span className="value">{formatSize(row.size, i18n.language)}</span>
          </>
        )}
      </p>
      {row.job_hash && outcome === undefined && (
        <p className="pl-7 text-xs text-ink-dim">
          {t('rss.oneshot.hasJob')} <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
        </p>
      )}
      {row.known !== null && (
        <p className="pl-7 text-xs wrap-anywhere text-ink-dim">
          {t('rss.oneshot.known', { known: row.known })}
        </p>
      )}
      {outcome && <Result outcome={outcome} />}
    </div>
  )
}

function Result({ outcome }: { outcome: Outcome }) {
  const { t } = useTranslation()
  if (outcome.kind === 'refused') {
    return (
      <div className="grid gap-1 pl-7">
        <p className="max-w-prose text-xs text-blocked-ink">
          {t(`jobs.refusal.${outcome.reason}`)}
        </p>
        {/* `job_removed` 的 `detail` 是那一筆的 hash：下一步在它的詳情頁上（同 `SubmitAction`）。 */}
        {outcome.reason === 'job_removed' ? (
          <p className="text-xs">
            <JobLink hash={outcome.detail}>{t('submit.toRemovedJob')}</JobLink>
          </p>
        ) : (
          outcome.detail && (
            <p className="value text-xs wrap-anywhere text-ink-dim">{outcome.detail}</p>
          )
        )}
      </div>
    )
  }
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 pl-7 text-xs">
      <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.secured}`}>
        {t(`rss.oneshot.outcome.${outcome.kind}`)}
      </span>
      <JobLink hash={outcome.hash}>{t('rss.items.job')}</JobLink>
    </p>
  )
}

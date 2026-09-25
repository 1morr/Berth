import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  parseRssRefusal,
  previewQueryOptions,
  primeFeed,
  RSS_KEY,
  type Feed,
  type FeedItem,
  type PrimeMode,
} from '../api/rss'
import { ConfirmAction, GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { whenText } from '../components/queueText'
import { SIGNAL_FILL } from '../components/signal'
import { JobLink } from '../jobs/JobLink'
import { formatSize } from '../media/searchResult'
import { maskToken } from './maskToken'
import { SectionHeading } from './SectionHeading'
import { skipText } from './skip'

/**
 * 等你決定：新 Feed 的第一輪（`.scratch/m3/preview-shape.md`，M3 票 11、brief §15）。
 *
 * 搜尋 feed（Nyaa、acg.rip）第一輪就帶著幾個月的歷史，所以 `primed_at` 還是 `null` 的 Feed 一筆都不送，
 * 停在這裡等使用者選「只追之後的」或「全部下載」。放在頁首（Needs-You Floats Up），選完那一塊消失。
 * Mikan 加的那一刻就算選過，不會出現在這裡。
 */
export function FirstRoundSection({
  feeds,
  onDone,
}: {
  feeds: Feed[]
  onDone: (said: string) => void
}) {
  const { t } = useTranslation()
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.first.title')}
        extra={
          <span className={`label px-2 py-1 ${SIGNAL_FILL.assigned}`}>
            {t('rss.first.chip', { count: feeds.length })}
          </span>
        }
      />
      <p className="max-w-prose text-sm text-ink-dim">{t('rss.first.lede')}</p>
      <ul className="grid gap-3">
        {feeds.map((feed) => (
          <li key={feed.id} className="min-w-0">
            <FirstRound feed={feed} onDone={onDone} />
          </li>
        ))}
      </ul>
    </section>
  )
}

/** 預覽的四組，照「全部下載」之後會怎樣分。空的組不出現。 */
type Outcome = 'send' | 'bind' | 'excluded' | 'duplicate'
const OUTCOMES: readonly Outcome[] = ['send', 'bind', 'excluded', 'duplicate']

function outcomeOf(row: FeedItem): Outcome | null {
  switch (row.status) {
    case 'matched':
      return 'send'
    case 'unbound':
      return 'bind'
    case 'excluded':
      return 'excluded'
    case 'duplicate':
      return 'duplicate'
    default:
      // 已送單與略過的不會出現在還沒選的 Feed 裡；真的有就不列。
      return null
  }
}

function FirstRound({ feed, onDone }: { feed: Feed; onDone: (said: string) => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  // 還沒讀過的不讓人選：沒看過的東西不選「全部下載」（shape §2）。
  const read = feed.last_polled_at !== null
  const preview = useQuery({ ...previewQueryOptions(feed.id), enabled: read })
  const prime = useMutation({
    mutationFn: (mode: PrimeMode) => primeFeed(feed.id, mode),
    onSuccess: async (outcome, mode) => {
      onDone(
        mode === 'later'
          ? t('rss.first.donePassed', { name: feed.name, count: outcome.passed })
          : t('rss.first.doneSent', { name: feed.name, count: outcome.submitted }),
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: RSS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
      ])
    },
    onError: async (error) => {
      // 另一個分頁先選了：重讀清單，這一塊自然消失。
      if (parseRssRefusal(error)?.reason === 'feed_primed') {
        await queryClient.invalidateQueries({ queryKey: RSS_KEY })
      }
    },
  })
  const refusal = prime.isError ? parseRssRefusal(prime.error) : null

  const groups = new Map<Outcome, FeedItem[]>()
  for (const row of preview.data ?? []) {
    const outcome = outcomeOf(row)
    if (outcome !== null) groups.set(outcome, [...(groups.get(outcome) ?? []), row])
  }
  const count = (outcome: Outcome) => groups.get(outcome)?.length ?? 0

  return (
    <article
      tabIndex={-1}
      aria-labelledby={headingId}
      className="grid gap-3 border-2 border-rule-strong bg-well px-4 py-3"
    >
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="label bg-deck px-2 py-1.5 text-ink">{t(`rss.kind.${feed.kind}`)}</span>
          <h3 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
            {feed.name}
          </h3>
        </div>
        <p className="value text-xs wrap-anywhere text-ink-dim">{maskToken(feed.url)}</p>
      </div>

      {!read ? (
        <p className="max-w-prose text-sm text-ink">{t('rss.first.unread')}</p>
      ) : preview.isPending ? (
        <div className="h-24 border-2 border-rule bg-hull" aria-hidden="true" />
      ) : preview.isError ? (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('rss.failed')}
        </Notice>
      ) : (
        <>
          <p className="value text-sm text-ink">
            {OUTCOMES.map((outcome, index) => (
              <span key={outcome} className="whitespace-nowrap">
                {index > 0 && (
                  <>
                    {' '}
                    <Dot />{' '}
                  </>
                )}
                {t(`rss.first.tally.${outcome}`, { count: count(outcome) })}
              </span>
            ))}
          </p>
          {refusal?.reason === 'feed_unreachable' ? (
            <Notice signal="blocked" label={t('common.failed')}>
              {t('rss.refusal.feed_unreachable')}{' '}
              <span className="value text-xs wrap-anywhere">{refusal.detail}</span>
            </Notice>
          ) : (
            prime.isError &&
            refusal?.reason !== 'feed_primed' && (
              <Notice signal="blocked" label={t('common.failed')}>
                {t('rss.failed')}
              </Notice>
            )
          )}

          <div className="grid gap-2 sm:flex sm:flex-wrap sm:items-start">
            <div className="sm:w-auto sm:min-w-64">
              <PrimaryButton
                type="button"
                busy={prime.isPending && prime.variables === 'later'}
                disabled={prime.isPending}
                onClick={() => prime.mutate('later')}
              >
                {prime.isPending && prime.variables === 'later'
                  ? t('rss.first.priming')
                  : t('rss.first.later')}
              </PrimaryButton>
            </div>
            <ConfirmAction
              label={t('rss.first.all')}
              confirmLabel={t('rss.first.allConfirm')}
              warning={t('rss.first.allWarning', { send: count('send'), bind: count('bind') })}
              pending={prime.isPending && prime.variables === 'all'}
              pendingLabel={t('rss.first.priming')}
              onConfirm={() => prime.mutate('all')}
            />
          </div>
          <p className="max-w-prose text-xs text-ink-dim">{t('rss.first.laterHint')}</p>
          {/* 決定在上、證據在下：22 筆的清單不能把兩顆鍵推出畫面（窄版尤其）。 */}
          <div className="grid gap-px bg-rule">
            {OUTCOMES.filter((outcome) => count(outcome) > 0).map((outcome) => (
              <Group
                key={outcome}
                outcome={outcome}
                rows={groups.get(outcome) ?? []}
                // 會下載的兩組一直攤開；不會下載的兩組先收起，要看為什麼再打開（shape §3）。
                folds={outcome === 'excluded' || outcome === 'duplicate'}
              />
            ))}
          </div>
        </>
      )}
    </article>
  )
}

function Group({
  outcome,
  rows,
  folds,
}: {
  outcome: Outcome
  rows: FeedItem[]
  /** 可以收起、而且一開始是收起的。 */
  folds: boolean
}) {
  const { t, i18n } = useTranslation()
  const [shown, setShown] = useState(!folds)
  const listId = useId()
  const name = t(`rss.first.group.${outcome}`, { count: rows.length })

  return (
    <div className="grid gap-2 bg-well py-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h4 className="label text-ink">{name}</h4>
        {folds && (
          <GhostButton
            type="button"
            aria-expanded={shown}
            aria-controls={listId}
            onClick={() => setShown(!shown)}
          >
            {shown ? t('common.collapseNamed', { name }) : t('rss.first.show', { name })}
          </GhostButton>
        )}
      </div>
      {outcome === 'bind' && (
        <p className="max-w-prose text-xs text-ink-dim">{t('rss.first.bindHint')}</p>
      )}
      {shown && (
        <ul id={listId} className="grid gap-px bg-rule">
          {rows.map((row) => (
            <li key={row.id} className="grid min-w-0 gap-1 bg-hull px-3 py-2">
              <span className="value text-sm wrap-anywhere text-ink">{row.title}</span>
              <p className="text-xs text-ink-dim">
                {t('rss.items.published')}{' '}
                <span className="value">
                  {row.published_at ? whenText(row.published_at, i18n.language) : '—'}
                </span>
                {row.size !== null && (
                  <>
                    {' '}
                    <Dot /> <span className="value">{formatSize(row.size, i18n.language)}</span>
                  </>
                )}
                {row.job_hash && (
                  <>
                    {' '}
                    <Dot /> <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
                  </>
                )}
              </p>
              {row.skip && (
                <p className="max-w-prose text-xs wrap-anywhere text-ink-dim">
                  {skipText(t, row.skip)}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

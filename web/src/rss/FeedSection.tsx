import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import {
  addFeed,
  deleteFeed,
  parseRssRefusal,
  pollFeed,
  RSS_KEY,
  type Feed,
  type PollOutcome,
} from '../api/rss'
import {
  ConfirmAction,
  Field,
  GHOST_LINK,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import { maskToken } from './maskToken'
import { SectionHeading } from './SectionHeading'

/**
 * Feed 段（`.scratch/m3/rss-shape.md` §2 第 2 段）：新增表單與每一個 Feed。
 *
 * 間隔不在表單上（預設 15 分鐘，plan §3.2）；編輯與停用沒有消費者就不做（shape §6）。
 */
export function FeedSection({ feeds }: { feeds: Feed[] }) {
  const { t } = useTranslation()
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.feeds.title')}
        count={{ value: feeds.length, spoken: t('rss.feeds.count', { count: feeds.length }) }}
      />
      {feeds.length === 0 && (
        // 空狀態（DESIGN.md）：一句 `ink` 散文加一條下一步。下一步在 Mikan 那一頭：訂閱之後才有網址可貼。
        <div className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
          <p className="max-w-prose text-sm text-ink">{t('rss.feeds.empty')}</p>
          <a href="https://mikanani.me/" target="_blank" rel="noreferrer" className={GHOST_LINK}>
            {t('rss.feeds.toMikan')}
          </a>
        </div>
      )}
      {feeds.length > 0 && (
        <ul className="grid gap-3">
          {feeds.map((feed) => (
            <li key={feed.id} className="min-w-0">
              <FeedRow feed={feed} />
            </li>
          ))}
        </ul>
      )}
      <AddFeed />
    </section>
  )
}

function AddFeed() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const add = useMutation({
    mutationFn: () => addFeed(url.trim(), name.trim()),
    onSuccess: async () => {
      setUrl('')
      setName('')
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const refusal = add.isError ? parseRssRefusal(add.error) : null

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (url.trim() !== '') add.mutate()
  }

  return (
    <form onSubmit={submit} className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
      <p className="label text-ink-dim">{t('rss.feeds.add')}</p>
      <Field
        label={t('rss.feeds.url')}
        hint={t('rss.feeds.urlHint')}
        type="url"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        required
        value={url}
        error={
          refusal ? t(`rss.refusal.${refusal.reason}`) : add.isError ? t('rss.failed') : undefined
        }
        onChange={(event) => setUrl(event.target.value)}
      />
      <Field
        label={t('rss.feeds.name')}
        hint={t('rss.feeds.nameHint')}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <div className="sm:max-w-xs">
        <PrimaryButton type="submit" busy={add.isPending} disabled={url.trim() === ''}>
          {add.isPending ? t('rss.feeds.adding') : t('rss.feeds.addAction')}
        </PrimaryButton>
      </div>
    </form>
  )
}

function FeedRow({ feed }: { feed: Feed }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const [polled, setPolled] = useState<PollOutcome | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: RSS_KEY })
  const poll = useMutation({
    mutationFn: () => pollFeed(feed.id),
    onMutate: () => setPolled(null),
    onSuccess: async (outcome) => {
      setPolled(outcome)
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ['jobs'] })])
    },
  })
  const remove = useMutation({ mutationFn: () => deleteFeed(feed.id), onSuccess: refresh })

  return (
    <article
      tabIndex={-1}
      aria-labelledby={headingId}
      className={`grid gap-2 border-2 bg-well px-4 py-3 ${
        feed.last_error ? 'border-rule-strong' : 'border-rule'
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-2 py-1.5 text-ink">{t(`rss.kind.${feed.kind}`)}</span>
        <h3 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
          {feed.name}
        </h3>
      </div>
      {/* 聚合 feed 的 token 就是憑證：畫面上不整串印出來（`maskToken`）。 */}
      <p className="value text-xs wrap-anywhere text-ink-dim">{maskToken(feed.url)}</p>
      <p className="text-xs text-ink-dim">
        {t('rss.feeds.every', { minutes: Math.round(feed.interval_sec / 60) })} <Dot />{' '}
        {t('rss.feeds.polled')} <Timestamp at={feed.last_polled_at} /> <Dot />{' '}
        <span className="value">{t('rss.feeds.items', { count: feed.items })}</span>
      </p>
      {feed.last_error && (
        <Notice signal="assigned" label={t('rss.feeds.failed')}>
          <span className="value text-xs wrap-anywhere">{feed.last_error}</span>
        </Notice>
      )}
      <p role="status" className="text-xs text-ink">
        {polled &&
          t('rss.feeds.polledNow', {
            items: polled.items,
            series: polled.series,
            sent: polled.submitted,
          })}
      </p>
      {(poll.isError || remove.isError) && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('rss.failed')}
        </Notice>
      )}
      <div className="flex flex-wrap items-start gap-2">
        <GhostButton type="button" busy={poll.isPending} onClick={() => poll.mutate()}>
          {poll.isPending ? t('rss.feeds.polling') : t('rss.feeds.poll')}
        </GhostButton>
        <ConfirmAction
          label={t('rss.feeds.delete')}
          confirmLabel={t('rss.feeds.deleteConfirm')}
          warning={t('rss.feeds.deleteWarning', { count: feed.items })}
          pending={remove.isPending}
          pendingLabel={t('rss.feeds.deleting')}
          onConfirm={() => remove.mutate()}
        />
      </div>
    </article>
  )
}

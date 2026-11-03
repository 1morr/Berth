import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import {
  OVERDUE_DAYS_MAX,
  overdueQueryOptions,
  RSS_KEY,
  saveSeriesOverdue,
  type RssSeries,
} from '../api/rss'
import { Field, GhostButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'

/**
 * 這個字幕組的遲到門檻（M5.5 票 11）：覆寫訂閱頁上方的全域門檻，留空回到全域。一部作品幾個字幕組時巡檢取
 * 最大值。形狀照全域那一格（`OverdueSection`），收在 RSS Series 展開區的「進階」。
 */
export function SeriesOverdue({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const global = useQuery(overdueQueryOptions())
  const [draft, setDraft] = useState<string | null>(null)
  const value = draft ?? (row.overdue_days === null ? '' : String(row.overdue_days))
  const trimmed = value.trim()
  const valid = trimmed === '' || (/^\d+$/.test(trimmed) && Number(trimmed) <= OVERDUE_DAYS_MAX)

  const save = useMutation({
    mutationFn: () => saveSeriesOverdue(row.id, trimmed === '' ? null : Number(trimmed)),
    onSuccess: async () => {
      setDraft(null)
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const invalid =
    (draft !== null && !valid) || (save.error instanceof ApiError && save.error.status === 422)

  return (
    <form
      noValidate
      className="grid gap-2 sm:max-w-xs"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid) save.mutate()
      }}
    >
      <Field
        label={t('rss.overdue.seriesLabel')}
        type="text"
        inputMode="numeric"
        value={value}
        onChange={(event) => setDraft(event.target.value)}
        hint={
          global.data
            ? t('rss.overdue.seriesHint', { days: global.data.days })
            : t('rss.overdue.seriesHintPlain')
        }
        error={invalid ? t('rss.overdue.seriesInvalid') : undefined}
      />
      <div className="flex flex-wrap items-center gap-3">
        <GhostButton type="submit" busy={save.isPending}>
          {save.isPending ? t('rss.overdue.saving') : t('rss.overdue.seriesSave')}
        </GhostButton>
        <p aria-live="polite" className="text-xs text-ink-dim">
          {save.isSuccess && draft === null ? t('rss.overdue.saved') : ''}
        </p>
      </div>
      {save.isError && !invalid && (
        <RequestFailed error={save.error} lead={t('rss.overdue.failed')} />
      )}
    </form>
  )
}

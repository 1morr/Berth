import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { OVERDUE_DAYS_MAX, overdueQueryOptions, saveOverdue } from '../api/rss'
import { Field, GhostButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SectionHeading } from '../components/SectionHeading'

/**
 * 遲到門檻（M5.5 票 10，2026-11-04 使用者定放在這裡）：訂閱的作品一集播出後幾天沒入庫，每日巡檢開
 * `episodes_overdue`。與全域排除條件同在訂閱頁，是 RSS 的全域那一層（`RssSettings`）。
 *
 * 形狀照設定頁的磁碟門檻（一個整數、存一下）。存了不當場重算：判定要讀 TMDB 與每一筆 Job，交給下一輪
 * 巡檢。中性、不塗漆：是設定，不是要你現在做的事。
 */
export function OverdueSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const current = useQuery(overdueQueryOptions())
  const [draft, setDraft] = useState<string | null>(null)
  const value = draft ?? (current.data ? String(current.data.days) : '')
  const trimmed = value.trim()
  const valid = /^\d+$/.test(trimmed) && Number(trimmed) <= OVERDUE_DAYS_MAX

  const save = useMutation({
    mutationFn: () => saveOverdue(Number(trimmed)),
    onSuccess: (fresh) => {
      queryClient.setQueryData(overdueQueryOptions().queryKey, fresh)
      setDraft(null)
    },
  })
  const invalid =
    (draft !== null && !valid) || (save.error instanceof ApiError && save.error.status === 422)

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading id={headingId} label={t('rss.overdue.title')} />
      <div className="grid gap-4 border-2 border-rule bg-well px-4 py-3">
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.overdue.lede')}</p>
        {current.isError ? (
          <RequestFailed error={current.error} lead={t('request.notDone')} />
        ) : (
          <form
            noValidate
            className="grid gap-3 sm:max-w-xs"
            onSubmit={(event) => {
              event.preventDefault()
              if (valid) save.mutate()
            }}
          >
            <Field
              label={t('rss.overdue.label')}
              type="text"
              inputMode="numeric"
              value={value}
              onChange={(event) => setDraft(event.target.value)}
              hint={t('rss.overdue.hint')}
              error={invalid ? t('rss.overdue.invalid') : undefined}
            />
            <div className="flex flex-wrap items-center gap-3">
              <GhostButton type="submit" busy={save.isPending}>
                {save.isPending ? t('rss.overdue.saving') : t('rss.overdue.save')}
              </GhostButton>
              <p aria-live="polite" className="text-xs text-ink-dim">
                {save.isSuccess ? t('rss.overdue.saved') : ''}
              </p>
            </div>
            {save.isError && !invalid && (
              <RequestFailed error={save.error} lead={t('rss.overdue.failed')} />
            )}
          </form>
        )}
      </div>
    </section>
  )
}

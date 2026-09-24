import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { rematchRefusalText } from '../api/files'
import {
  decideDuplicate,
  reviewQueryOptions,
  type DuplicateDecision,
  type DuplicateReviewRow,
} from '../api/review'
import { ConfirmAction, GhostButton } from '../components/controls'
import { formatEpisode } from '../components/episodes'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { fileName, whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'

/**
 * 規劃時與媒體庫裡已有的一份重複、自動模式先略過的檔案（brief §7.8、M2 票 08）。
 *
 * 句子依理由說出**後果**：同一個版本就只是重複；起始集相同而結束集不同的那一種，兩份都留的話
 * Jellyfin 12 會把它們併成同一集的兩個版本、後面那一集從集列表消失（§20.9）。三顆：
 *
 * - **取代舊版**就地確認：媒體庫裡舊的那一份（連同它的字幕）會被拿掉——破壞性（原則 2）。
 * - **保留兩者**：同一個版本時不確認，新的檔名多一個序號標籤（展開區說）；範圍不同時就地確認，
 *   因為那正是會讓一集從列表上消失的那一步。
 * - **跳過**不確認：什麼都不動。
 */
export function DuplicateRow({
  row,
  onDone,
}: {
  row: DuplicateReviewRow
  onDone: (said: string) => void
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)
  const clash = row.reason.code === 'span_clash'

  const decide = useMutation({
    mutationFn: (decision: DuplicateDecision) => decideDuplicate(row.ref, decision),
    onMutate: () => setRefusal(null),
    onSuccess: (_, decision) => {
      onDone(t(`review.duplicate.done.${decision}`))
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      void queryClient.invalidateQueries({ queryKey: ['media'] })
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error) => {
      setRefusal(rematchRefusalText(t, error))
      // 另一個分頁先決定了：重問一次，那一列自己消失。
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
    },
  })

  const busy = decide.isPending
  const title = displayRound(i18n.language, { 'zh-Hant': row.title, en: row.title_en })
  const episode = formatEpisode(row)
  const known = formatEpisode({
    season: row.known_season,
    episode_start: row.known_episode_start,
    episode_end: row.known_episode_end,
  })

  return (
    <QueueRow
      label={t('review.duplicate.label')}
      heading="h3"
      title={title ? [title, episode].filter(Boolean).join(' ') : fileName(row.path)}
      sentence={t(`review.duplicate.reason.${row.reason.code}`)}
      when={t('review.duplicate.skippedAt', { value: whenText(row.at, i18n.language) })}
      refusal={refusal}
      details={
        <>
          <DetailLine term={t('review.duplicate.path')}>
            {[episode, row.path].filter(Boolean).join(' · ')}
          </DetailLine>
          <DetailLine term={t('review.duplicate.known')}>
            {[known, row.known_path].filter(Boolean).join(' · ')}
          </DetailLine>
          <DetailLine term={t('review.duplicate.job')}>
            <JobLink hash={row.job_hash}>{row.job_name}</JobLink>
          </DetailLine>
          {!clash && (
            <DetailLine term={t('review.duplicate.action.keep_both')}>
              {t('review.duplicate.keepBothHint')}
            </DetailLine>
          )}
        </>
      }
    >
      {row.actions.map((decision) =>
        decision === 'replace' || (decision === 'keep_both' && clash) ? (
          <ConfirmAction
            key={decision}
            label={t(`review.duplicate.action.${decision}`)}
            confirmLabel={
              decision === 'replace'
                ? t('review.duplicate.confirmReplaceAction')
                : t('review.duplicate.confirmKeepClashAction')
            }
            warning={
              decision === 'replace'
                ? t('review.duplicate.confirmReplace')
                : t('review.duplicate.confirmKeepClash')
            }
            pending={busy}
            pendingLabel={t('review.duplicate.working')}
            onConfirm={() => decide.mutate(decision)}
          />
        ) : (
          <GhostButton
            key={decision}
            type="button"
            disabled={busy}
            onClick={() => decide.mutate(decision)}
          >
            {busy ? t('review.duplicate.working') : t(`review.duplicate.action.${decision}`)}
          </GhostButton>
        ),
      )}
    </QueueRow>
  )
}

import { useTranslation } from 'react-i18next'

import type { UnmatchedReviewRow } from '../api/review'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { fileName, whenText } from '../components/queueText'
import { RematchForm } from '../components/RematchForm'
import { displayRound } from '../i18n/displayRound'
import { Reasons } from '../plans/Reasons'

/**
 * 一個對不到、留在 complete 原位的檔案（brief §7.4、M2 票 08）。
 *
 * **表單就是這一列的工作**，攤開不收：指派到某一集、標記為特典、忽略三選一，季集就地填
 * （brief §7.6：「把這檔指派為 S00E03 只需兩次點擊」）。與 Media 詳情的 Unmatched 區是同一個表單、
 * 打同一支（`RematchForm`）。這個檔案不在媒體庫裡，沒有東西會被拿掉，所以不另外確認。
 */
export function UnmatchedRow({
  row,
  onDone,
}: {
  row: UnmatchedReviewRow
  onDone: (said: string) => void
}) {
  const { t, i18n } = useTranslation()
  const title = displayRound(i18n.language, { 'zh-Hant': row.title, en: row.title_en })

  return (
    <QueueRow
      label={t('review.unmatched.label')}
      heading="h3"
      // 檔名是使用者認得出這一個檔案的東西；作品名在前面說它屬於哪一部。
      title={[title, fileName(row.path)].filter(Boolean).join(' · ')}
      sentence={t(`review.unmatched.reason.${row.reason.code}`)}
      when={t('review.unmatched.waitingSince', { value: whenText(row.at) })}
      refusal={null}
      body={
        <RematchForm
          subject={{ job_file_id: row.ref }}
          actions={row.actions}
          mediaKind={row.media_kind}
          linked={false}
          onDone={onDone}
        />
      }
      details={
        <>
          <DetailLine term={t('review.unmatched.path')}>{row.path}</DetailLine>
          <DetailLine term={t('review.unmatched.job')}>
            <JobLink hash={row.job_hash}>{row.job_name}</JobLink>
          </DetailLine>
          {row.reasons.length > 0 && (
            <DetailLine term={t('review.unmatched.reasons')}>
              <Reasons reasons={row.reasons} />
            </DetailLine>
          )}
        </>
      }
    />
  )
}

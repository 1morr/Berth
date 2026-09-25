import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  confirmAudits,
  confirmSeries,
  reviewQueryOptions,
  type AuditReviewRow,
  type AuditsConfirmed,
} from '../api/review'

/** 按完之後要說的那一句。`shown`：整組或整段一次消失時，結果要看得見，不只念給螢幕閱讀器聽。 */
export type Said = (said: string, shown?: boolean) => void

/**
 * 「全部確認」（M3 票 05、13）：同一個 RSS Series 或同一個 Job 那一組，與 audit 段整段共用。送的是呼叫端
 * **當下列出的**那幾列。
 *
 * **RSS Series 送的列打 Series 那一支**（`confirmRows`）：逐列確認之外還把 Series 標成確認過。整段的那一顆
 * 也是——按下去的人說的是「這些都對」，第一批確認過了，Series 卻還等著確認，下一集又會掛上第一批。
 *
 * 後端把已經被別處確認或撤銷的列跳過、不當失敗，所以這裡沒有拒絕要翻；會失敗的只有網路。結果照實說出
 * 確認了幾個、跳過了幾個——跳過的那幾個不說的話，數字對不上使用者剛剛看到的列數。
 */
export function useConfirmAudits(onDone: Said) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [failed, setFailed] = useState<string | null>(null)

  const act = useMutation({
    mutationFn: confirmRows,
    onMutate: () => setFailed(null),
    onSuccess: ({ confirmed, skipped }) => {
      onDone(
        [
          confirmed > 0 ? t('review.audit.confirmedMany', { count: confirmed }) : '',
          skipped > 0 ? t('review.audit.skipped', { count: skipped }) : '',
        ]
          .filter(Boolean)
          .join(' '),
        true,
      )
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      // 下載列表那一列的「N 個待確認」數的是同一組旗標，Media 詳情的也是（M3 票 06）。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      void queryClient.invalidateQueries({ queryKey: ['media'] })
    },
    onError: () => {
      setFailed(t('review.audit.failed'))
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
    },
  })

  return { confirm: act.mutate, pending: act.isPending, failed }
}

/** 依 RSS Series 分開送：一個 Series 一次（`/review/series/{id}/confirm`），其餘一次，件數加總。 */
async function confirmRows(rows: readonly AuditReviewRow[]): Promise<AuditsConfirmed> {
  const bySeries = new Map<number, number[]>()
  const loose: number[] = []
  for (const row of rows) {
    if (row.series === null) loose.push(row.ref)
    else bySeries.set(row.series.id, [...(bySeries.get(row.series.id) ?? []), row.ref])
  }
  const outcomes = await Promise.all([
    ...[...bySeries].map(([seriesId, ids]) => confirmSeries(seriesId, ids)),
    ...(loose.length > 0 ? [confirmAudits(loose)] : []),
  ])
  return outcomes.reduce(
    (sum, outcome) => ({
      confirmed: sum.confirmed + outcome.confirmed,
      skipped: sum.skipped + outcome.skipped,
    }),
    { confirmed: 0, skipped: 0 },
  )
}

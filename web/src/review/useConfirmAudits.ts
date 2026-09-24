import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { confirmAudits, reviewQueryOptions } from '../api/review'

/** 按完之後要說的那一句。`shown`：整組或整段一次消失時，結果要看得見，不只念給螢幕閱讀器聽。 */
export type Said = (said: string, shown?: boolean) => void

/**
 * 「全部確認」（M3 票 05）：同一個 Job 那一組與 audit 段整段共用。送的是呼叫端**當下列出的**那幾個 id。
 *
 * 後端把已經被別處確認或撤銷的列跳過、不當失敗，所以這裡沒有拒絕要翻；會失敗的只有網路。結果照實說出
 * 確認了幾個、跳過了幾個——跳過的那幾個不說的話，數字對不上使用者剛剛看到的列數。
 */
export function useConfirmAudits(onDone: Said) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [failed, setFailed] = useState<string | null>(null)

  const act = useMutation({
    mutationFn: (ledgerIds: readonly number[]) => confirmAudits(ledgerIds),
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

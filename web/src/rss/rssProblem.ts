import type { TFunction } from 'i18next'

import { parseRssRefusal } from '../api/rss'
import { problemText } from '../components/requestProblem'

/**
 * `/rss` 的請求沒成時欄位下的那一句：`rule_invalid` 帶著 Python `re` 的原文，其他拒絕照 code
 * 挑句子（`rss.refusal.*`），不是拒絕的落回通用的請求問題。
 */
export function rssProblem(t: TFunction, error: unknown): string {
  const refusal = parseRssRefusal(error)
  return refusal?.reason === 'rule_invalid'
    ? t('rss.rules.invalid', { detail: refusal.detail })
    : refusal
      ? t(`rss.refusal.${refusal.reason}`)
      : problemText(t, error, t('request.notDone'))
}

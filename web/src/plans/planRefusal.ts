import type { TFunction } from 'i18next'

import { parsePlanRefusal } from '../api/plans'

/** 改、核准、拒絕被擋下來時那一句：理由翻譯，`detail`（檔名或路徑）原文接在後面。 */
export function planRefusalText(t: TFunction, error: unknown): string {
  const said = parsePlanRefusal(error)
  if (!said) return t('review.plan.failed')
  return [t(`review.plan.refusal.${said.reason}`), said.detail].filter(Boolean).join(' ')
}

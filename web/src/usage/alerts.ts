import type { TFunction } from 'i18next'

import type { SpendAlert } from '../api/usage'
import { usd } from './numbers'

/**
 * 一則花費提醒的那一句（M5 票 21）：用量頁說得完整，側面板說短的。只提醒、不停用。
 * 異常的倍數取整數：「16 倍」比「15.7 倍」好讀，而門檻是 5 倍，不會被四捨五入騙到。
 */
export function alertText(
  t: TFunction,
  alert: SpendAlert,
  language: string,
  where: 'page' | 'panel',
): string {
  const today = Number(alert.today)
  const against = Number(alert.against)
  const values = { today: usd(today, language), against: usd(against, language) }
  if (alert.kind === 'threshold') {
    return where === 'page'
      ? t('usage.alerts.threshold', values)
      : t('agent.spend.threshold', values)
  }
  const times = Math.round(today / against)
  return where === 'page'
    ? t('usage.alerts.anomaly', { ...values, times })
    : t('agent.spend.anomaly', { ...values, times })
}

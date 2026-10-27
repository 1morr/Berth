import type { TFunction } from 'i18next'

import type { SpendAlert, SpendCheck } from '../api/usage'
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

/**
 * 提醒沒算進去的那一句（協調者 2026-10-27）：提醒只用知道的費用比，費用未知的呼叫（模型不在價目表上，
 * 有回應、有 token 而價目查不到的；出錯沒有回應的沒有花費，不數）不在裡面。沒有這一句的話，「沒有提醒」看起來就像沒事。都知道是 `null`。
 */
export function unknownText(
  t: TFunction,
  spend: SpendCheck,
  where: 'page' | 'panel',
): string | null {
  const count = spend.unknown_today + spend.unknown_before
  if (count === 0) return null
  return where === 'page'
    ? t('usage.alerts.unknown', {
        count,
        today: spend.unknown_today,
        before: spend.unknown_before,
      })
    : t('agent.spend.unknown', { count })
}

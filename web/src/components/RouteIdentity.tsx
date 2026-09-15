import { useTranslation } from 'react-i18next'

import type { RouteView } from '../api/schemas'
import { ROUTE_HEALTH_LABEL, ROUTE_SIGNAL } from './routeChecks'
import { SIGNAL_FILL } from './signal'

/**
 * 一條 Route 的身分帶：健康色塊、停用色塊、名稱、category（票 14）。
 *
 * 健康頁與 Route 設定頁的那一列共用——同一件事不該有兩種畫法。停用不是四個信號之一，用中性
 * 色塊（DESIGN.md 的 The Role Is Not A State Rule 同一個道理）；它照樣檢查、照樣列出，但不算進
 * 健康總結，這一塊說出為什麼。回的是片段，排版由那一列自己的 `<summary>` 決定。
 */
export function RouteIdentity({ route }: { route: RouteView }) {
  const { t } = useTranslation()

  return (
    <>
      <span className={`label px-2 py-1.5 ${SIGNAL_FILL[ROUTE_SIGNAL[route.health]]}`}>
        {t(ROUTE_HEALTH_LABEL[route.health])}
      </span>
      {!route.enabled && (
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL.neutral}`}>
          {t('routeSettings.disabled')}
        </span>
      )}
      <span className="value text-sm font-semibold text-ink">{route.name}</span>
      <span className="value text-xs text-ink-dim">{route.category}</span>
    </>
  )
}

import { useTranslation } from 'react-i18next'

import { ROUTE_CHECKS, type RouteView } from '../api/schemas'
import { CHECK_COMMANDS, CHECK_ENDPOINT, CHECK_FIX, CHECK_LABEL } from './routeChecks'
import { StepLine } from './StepLine'

/**
 * 一個 Route 的五條纜繩（plan §9.5）。
 *
 * 精靈第 5 步與健康頁跑的是**同一組檢查、同一個欄位**，所以顯示它們的也是同一個元件——
 * 「精靈當時是綠的、現在紅了」在畫面上因此是同一種東西。失敗就地展開服務回的原文、
 * 該補哪個掛載，以及可以貼回 compose 的片段。
 */
export function RouteCheckList({ route, busy = false }: { route: RouteView; busy?: boolean }) {
  const { t } = useTranslation()
  const byCheck = new Map(route.checks.map((row) => [row.step, row]))

  return (
    <ol aria-live="polite" aria-busy={busy} className="grid gap-3" data-testid="checks">
      {ROUTE_CHECKS.map((check) => (
        <StepLine
          key={check}
          label={t(CHECK_LABEL[check])}
          endpoint={CHECK_ENDPOINT[check]}
          row={byCheck.get(check)}
          fix={t(CHECK_FIX[check])}
          commands={CHECK_COMMANDS[check]}
        >
          {check === 'hardlink' && route.cross_device && (
            <p className="mt-3 max-w-prose text-xs text-ink-dim">{t('routes.fix.crossDevice')}</p>
          )}
        </StepLine>
      ))}
    </ol>
  )
}

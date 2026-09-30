import { useTranslation } from 'react-i18next'

import { ROUTE_CHECKS, type RouteView } from '../api/schemas'
import { CHECK_ENDPOINT, CHECK_LABEL, type ExistingServices, remedyFor } from './routeChecks'
import { StepLine } from './StepLine'

/**
 * 一個 Route 的六條纜繩（plan §9.5）。
 *
 * 精靈頁 3 與健康頁跑的是**同一組檢查、同一個欄位**，所以顯示它們的也是同一個元件——
 * 「精靈當時是綠的、現在紅了」在畫面上因此是同一種東西。失敗就地展開服務回的原文、
 * 該改哪一台的掛載，以及可以貼回 compose 的片段（`remedyFor`）。
 *
 * **既有服務的補法是那一台自己的版本**（票 08、19，brief §16.4）：片段是「你那一份 compose」要加的，
 * 說明講同一台主機、同一個容器路徑、不做 remote path mapping。健康頁與設定頁讀不到來源，給套件內那一份。
 */
export function RouteCheckList({
  route,
  busy = false,
  existing,
}: {
  route: RouteView
  busy?: boolean
  existing?: ExistingServices
}) {
  const { t } = useTranslation()
  const byCheck = new Map(route.checks.map((row) => [row.step, row]))

  return (
    <ol aria-live="polite" aria-busy={busy} className="grid gap-3" data-testid="checks">
      {ROUTE_CHECKS.map((check) => {
        const remedy = remedyFor(check, { existing, crossDevice: route.cross_device })
        return (
          <StepLine
            key={check}
            label={t(CHECK_LABEL[check])}
            endpoint={CHECK_ENDPOINT[check]}
            row={byCheck.get(check)}
            fix={t(remedy.fix, { root: remedy.root })}
            commands={remedy.commands}
          >
            {check === 'hardlink' && route.cross_device && (
              <p className="mt-3 max-w-prose text-xs text-ink-dim">{t('routes.fix.crossDevice')}</p>
            )}
            {remedy.advice && (
              <p className="mt-3 max-w-prose text-xs text-ink">{t(remedy.advice)}</p>
            )}
          </StepLine>
        )
      })}
    </ol>
  )
}

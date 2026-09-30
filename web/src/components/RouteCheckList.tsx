import { useTranslation } from 'react-i18next'

import { ROUTE_CHECKS, type RouteCheck, type RouteView } from '../api/schemas'
import {
  CHECK_ENDPOINT,
  CHECK_LABEL,
  CHECK_SERVICE,
  type ExistingServices,
  remedyFor,
} from './routeChecks'
import { BAN_DEFAULTS } from './services'
import { StepLine } from './StepLine'

/**
 * 一個 Route 的六條纜繩（plan §9.5）。
 *
 * 精靈頁 3、健康頁與 Route 設定頁跑的是**同一組檢查、同一個欄位**，所以顯示它們的也是同一個元件——
 * 「精靈當時是綠的、現在紅了」在畫面上因此是同一種東西。失敗就地展開一句人話（後端的代碼選的，
 * M4 票 21）、該改哪一台的掛載，以及可以貼回 compose 的片段（`remedyFor`）；原文與端點收進技術細節。
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
        const row = byCheck.get(check)
        const remedy = remedyFor(check, {
          existing,
          crossDevice: route.cross_device,
          failure: row?.failure,
        })
        return (
          <StepLine
            key={check}
            label={t(CHECK_LABEL[check])}
            service={CHECK_SERVICE[check]}
            endpoint={CHECK_ENDPOINT[check]}
            summary={summaryOf(check, route)}
            row={row}
            fix={t(remedy.fix, {
              root: remedy.root,
              service: CHECK_SERVICE[check],
              ...BAN_DEFAULTS,
            })}
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

/**
 * 行首的關鍵值：這一條驗的是哪個名字或哪條路徑。由 Route 本身給，不從後端的 `detail` 拆——那一串是
 * 實測值（`dev=` / `inode=`、下載落在哪），收進技術細節。硬鏈接沒有一個名字可說。
 */
function summaryOf(check: RouteCheck, route: RouteView): string | undefined {
  switch (check) {
    case 'category':
      return route.category
    case 'download_path':
    case 'download_visible':
      return route.save_path
    case 'library_path':
    case 'probe_visible':
      return route.target_path
    case 'hardlink':
      return undefined
  }
}

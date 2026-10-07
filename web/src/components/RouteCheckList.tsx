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
import { Timestamp } from './Timestamp'

/**
 * 一個 Route 的六條纜繩（plan §9.5）。
 *
 * 精靈頁 3、健康頁與 Route 設定頁跑的是**同一組檢查、同一個欄位**，所以顯示它們的也是同一個元件——
 * 「精靈當時是綠的、現在紅了」在畫面上因此是同一種東西。失敗就地展開一句人話（後端的代碼選的，
 * M4 票 21）、該改哪一台的掛載，以及可以貼回 compose 的片段（`remedyFor`）；原文與端點收進技術細節。
 *
 * **既有服務的補法是那一台自己的版本**（票 08、19、36，brief §16.4）：片段是「你原本那一份」要多加的一條
 * （compose 與 `docker run` 各一種），說明講同一台主機、容器路徑只能是 `/data`、原本的掛載不動。精靈頁 3 與
 * Route 設定頁照選擇給（`existing`）；健康頁不給，用套件內那一份。
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
              // 那一條的參數先放：補法裡的 `{{root}}` 與 `{{service}}` 是這裡算的，不讓後端的同名參數蓋掉。
              path: '',
              ...row?.params,
              root: remedy.root,
              service: CHECK_SERVICE[check],
              ...BAN_DEFAULTS,
            })}
            commands={remedy.commands}
            note={check === 'download_visible' && route.probe_carried && <Carried route={route} />}
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
 * 健康迴圈沿用的探針結論（M4 票 19、50）：它不是這一輪問到的，說出是哪一次、為什麼沒重問、去哪裡重問。
 * 票 50 之前的結論沒有時間，`Timestamp` 說「沒有紀錄」。
 */
function Carried({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  return (
    <>
      <p>
        {t('routes.carried.label')} · <Timestamp at={route.probed_at} />
      </p>
      <p className="mt-1 max-w-prose">
        {t('routes.carried.why', { recheck: t('routeSettings.recheck') })}
      </p>
    </>
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

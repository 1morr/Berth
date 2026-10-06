import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { ROUTE_CHECKS, type RouteView } from '../api/schemas'
import { RouteIdentity } from './RouteIdentity'
import { CHECK_LABEL } from './routeChecks'
import { isSettled } from './steps'

/**
 * 一條 Route 收成一列（M4 票 08，`.scratch/m4/route-berth-shape.md`）：精靈頁 3、健康頁、Route 設定頁
 * 共用——同一件事不該有三種畫法。摘要是身分帶、寫入目標與「6 / 6 通過」，展開的內容由那一頁給。
 *
 * **紅的自己打開**（呼叫端給 `attention`）：需要人的那一條不必再按一下才看得到斷在哪裡，全綠的時候沒有人要讀
 * 那十幾行（GitHub Actions 的 job 列表同一個形狀）。原生 `<details>`：鍵盤與螢幕閱讀器的行為比自己管
 * state 好（M1 票 05 的決定）；`<summary>` 是 flex，三角形會被吃掉，展開與否由模板字自己說。
 */
export function RouteRow({
  route,
  attention,
  extra,
  expandLabel,
  collapseLabel,
  children,
}: {
  route: RouteView
  /**
   * 需要人看的那一條（紅燈；設定頁另算停用）：預設展開、框線加重。prop 變了（重新檢查之後轉紅）
   * 才跟著變，使用者自己開關的不蓋掉。
   */
  attention: boolean
  /** 摘要列上寫入目標之後的東西（設定頁的用量）。 */
  extra?: ReactNode
  expandLabel: string
  collapseLabel: string
  children: ReactNode
}) {
  return (
    <details
      open={attention}
      className={`group min-w-0 border-2 bg-well ${attention ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <RouteIdentity route={route} />
        {/* `wrap-anywhere` 而不是 `truncate`：三條 Route 常常只差路徑的最後一段
            （`/mnt/disk1/tv`、`/mnt/disk2/tv`），截掉尾巴之後窄版上三列一模一樣（M1 票 03 第 15 條）。 */}
        <span className="value min-w-0 grow wrap-anywhere text-xs text-ink-dim">
          {route.target_path}
        </span>
        <CheckTally route={route} />
        {extra}
        <span className="label shrink-0 text-ink-dim group-open:hidden">{expandLabel}</span>
        <span className="label hidden shrink-0 text-ink-dim group-open:inline">
          {collapseLabel}
        </span>
      </summary>
      <div className="grid gap-4 border-t-2 border-rule px-4 py-4">{children}</div>
    </details>
  )
}

/**
 * 「6 / 6 通過」。`skipped`（已經是這樣）也算通過，與纜繩列的塗法一致。一次都還沒檢查過的
 * 不畫：「0 / 6」讀起來像每一條都壞了，而健康色塊已經說了「尚未檢查」。
 *
 * 跑到一半時說跑到第幾條、是哪一條（M4 票 43）：每條纜繩開跑前後端先寫 `running`，頁 3 輪詢它。
 */
export function CheckTally({ route }: { route: RouteView }) {
  const { t } = useTranslation()
  if (route.checks.length === 0) return null
  const running = ROUTE_CHECKS.findIndex((check) =>
    route.checks.some((row) => row.step === check && row.status === 'running'),
  )
  if (running !== -1) {
    return (
      <span className="value shrink-0 text-xs text-ink">
        {t('routes.tallyRunning', {
          at: running + 1,
          total: ROUTE_CHECKS.length,
          check: t(CHECK_LABEL[ROUTE_CHECKS[running]!]),
        })}
      </span>
    )
  }
  const passed = route.checks.filter((row) => isSettled(row.status)).length

  return (
    <span className="value shrink-0 text-xs text-ink">
      {t('routes.tally', { passed, total: ROUTE_CHECKS.length })}
    </span>
  )
}

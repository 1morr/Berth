import { useTranslation } from 'react-i18next'

import { ROUTE_CHECKS, type RouteCheck, type RouteView } from '../api/schemas'
import { CHECK_COMMANDS, CHECK_ENDPOINT, CHECK_FIX, CHECK_LABEL } from './routeChecks'
import { StepLine } from './StepLine'

/** 哪幾個服務是使用者自己的那一台（M4 票 08）。只有精靈讀得到選擇，健康頁與設定頁不給。 */
export interface ExistingServices {
  jellyfin: boolean
  qbittorrent: boolean
}

/**
 * 一個 Route 的五條纜繩（plan §9.5）。
 *
 * 精靈頁 3 與健康頁跑的是**同一組檢查、同一個欄位**，所以顯示它們的也是同一個元件——
 * 「精靈當時是綠的、現在紅了」在畫面上因此是同一種東西。失敗就地展開服務回的原文、
 * 該補哪個掛載，以及可以貼回 compose 的片段。
 *
 * **既有服務另說同主機、同容器路徑的條件**（票 08，brief §16.4）：compose 片段是套件內那一份，
 * 使用者自己的 Jellyfin / qBittorrent 不在它裡面；它們失敗在第 2–5 條時，真正的原因多半是在另一台
 * 主機或掛在別的容器路徑，而 Berth 不做 remote path mapping。
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
        const remount = existing && remountAdvice(check, existing, route.cross_device)
        return (
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
            {remount && (
              <p className="mt-3 max-w-prose text-xs text-ink">{t(REMOUNT_ADVICE[remount])}</p>
            )}
          </StepLine>
        )
      })}
    </ol>
  )
}

const REMOUNT_ADVICE = {
  qbittorrent: 'routes.fix.existing.qbittorrent',
  jellyfin: 'routes.fix.existing.jellyfin',
  probe: 'routes.fix.existing.probe',
  split: 'routes.fix.existing.split',
} as const

/**
 * 這一條失敗時，要不要另說「改你自己那一台的掛載」、說哪一句。StepLine 只在失敗時畫 children，
 * 所以這裡只看是哪一條、牽涉哪一台。第 1 條（分類）與掛載無關。
 */
function remountAdvice(
  check: RouteCheck,
  existing: ExistingServices,
  crossDevice: boolean,
): keyof typeof REMOUNT_ADVICE | null {
  switch (check) {
    case 'download_path':
      return existing.qbittorrent ? 'qbittorrent' : null
    case 'library_path':
      return existing.jellyfin ? 'jellyfin' : null
    case 'probe_visible':
      return existing.jellyfin ? 'probe' : null
    case 'hardlink':
      return crossDevice && (existing.jellyfin || existing.qbittorrent) ? 'split' : null
    case 'category':
      return null
  }
}

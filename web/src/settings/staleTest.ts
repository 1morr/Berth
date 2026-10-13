import type { ServiceHealth } from '../api/health'
import type { SetupService } from '../api/setup'

/**
 * 通過的連線測試已經過時：之後的健康檢查連不上（M4 票 61，審計 S4：設定頁同時畫舊的綠色「連線測試通過」與
 * 紅色的健康卡）。測試沒通過、健康是綠的、或健康那一輪比測試舊時不算——那時候測試那一列說的就是現況。
 */
export function staleTest(
  service: SetupService | undefined,
  health: ServiceHealth | undefined,
): boolean {
  if (service?.state !== 'ok' || !service.checked_at) return false
  if (!health || health.unused || health.status !== 'failed' || !health.checked_at) return false
  return Date.parse(health.checked_at) > Date.parse(service.checked_at)
}

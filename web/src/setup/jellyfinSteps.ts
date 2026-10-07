import type { JellyfinSetup } from '../api/setup'
import { type SetupStep } from '../api/schemas'

/** 建媒體庫（或加路徑）那一步失敗了：它記在 Jellyfin 的 `libraries` 那一步上。 */
export function librariesFailed(jellyfin: JellyfinSetup): SetupStep | undefined {
  // 套件內清單全部已建立時，那次失敗是上一輪的事：使用者可能照手動步驟在 Jellyfin 補建了，而清單
  // 全建好時不再呼叫 bootstrap、那一步不會被改寫。後端判定頁 3 看的也是「已建立」（M4 票 24）。
  if (jellyfin.origin === 'bundled' && jellyfin.bundled.every((row) => row.built)) return undefined
  return jellyfin.steps.find((row) => row.step === 'libraries' && row.status === 'failed')
}

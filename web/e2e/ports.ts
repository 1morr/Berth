/**
 * e2e 演練伺服器的 port 整段位移（`E2E_PORT_OFFSET`）。
 *
 * `playwright.config.ts` 的每一條流程獨佔一台替身、一個固定 port（8484 起）。同一台機器上兩個 worktree 同時跑
 * `pnpm -C web e2e` 會搶同一組 port，後起的那一套在 `webServer` 就失敗（M5 票 15b 實跑撞到）。設了位移，
 * 整張表一起平移；不設是 0，port 照表，CI 不用改。
 */

/** 位移之後最小與最大的 port：1024 以下要權限，65535 以上不存在。 */
const LOWEST = 1024
const HIGHEST = 65535

/**
 * 讀 `E2E_PORT_OFFSET`。沒設或空字串是 0；不是整數，或位移之後有哪一個 port 落在 1024–65535 之外就丟錯——
 * 打錯的值在 playwright 起伺服器之前就說清楚，而不是變成一堆連不上。
 */
export function portOffset(raw: string | undefined, ports: readonly number[]): number {
  if (raw === undefined || raw.trim() === '') return 0
  const offset = Number(raw)
  if (!Number.isInteger(offset)) {
    throw new Error(`E2E_PORT_OFFSET must be an integer, got ${JSON.stringify(raw)}`)
  }
  const low = Math.min(...ports) + offset
  const high = Math.max(...ports) + offset
  if (low < LOWEST || high > HIGHEST) {
    throw new Error(
      `E2E_PORT_OFFSET=${offset} moves the e2e ports to ${low}–${high}, outside ${LOWEST}–${HIGHEST}`,
    )
  }
  return offset
}

import type { BerthSlot } from '../components/berths'

/**
 * 精靈的導覽（票 06d）。
 *
 * **步驟由後端狀態導出，不存游標**（plan §9.3）：後端說「現在是第幾步」，前端不改它。
 * 前端只有一個覆寫——`pinned`，畫面停在哪一步——而它的進出規則全部在這裡，是純函式：
 *
 * - 一個泊位做完，後端就前進了；畫面照樣停在那一步的結果上（按下動作的那一刻釘住），
 *   按「前往下一個泊位」才走。
 * - 走過的步驟點得回去，還沒到的點不過去——前進只能靠把事做完（Material Stepper 的 linear 模式）。
 * - 去後端目前那一頁（或更後面）就是解除覆寫，所以回頭之後永遠走得回來。
 *
 * 第 6、7 步（索引站、TMDB）現在是同一頁（泊位「來源」），票 06e 拆開之後 `pageOf` 的那一條就刪掉。
 */

/** plan §9.3 的八步。Route 排在 qBittorrent 之後（票 06d）。 */
export const STEP = {
  admin: 1,
  detect: 2,
  jellyfin: 3,
  qbittorrent: 4,
  routes: 5,
  indexer: 6,
  tmdb: 7,
  complete: 8,
} as const

export const TOTAL_STEPS = STEP.complete

/** 每個泊位是哪一步（那一頁的第一步）。泊位板點下去就去這一步。 */
export const BERTH_STEP = {
  jellyfin: STEP.jellyfin,
  qbittorrent: STEP.qbittorrent,
  library: STEP.routes,
  prowlarr: STEP.indexer,
} as const satisfies Record<BerthSlot, number>

/** 一步畫在哪一頁（以那一頁的第一步代表）。只有 TMDB 與索引站同一頁。 */
function pageOf(step: number): number {
  return step === STEP.tmdb ? STEP.indexer : step
}

/** 畫面上是哪一步。覆寫只能往回：後端退回去了的話，還沒到的那一步不能看。 */
export function shownStep(current: number, pinned: number | null): number {
  return pinned !== null && pageOf(pinned) <= pageOf(current) ? pinned : current
}

/** 去某一步之後的覆寫。去後端目前那一頁或更後面就是解除覆寫——不必記得另一顆「回到目前」。 */
export function go(target: number, current: number): number | null {
  return pageOf(target) >= pageOf(current) ? null : target
}

/** 下一頁的第一步。完成頁沒有下一個。 */
export function nextOf(step: number): number | null {
  const page = pageOf(step)
  if (page === STEP.indexer) return STEP.complete
  return page < STEP.complete ? page + 1 : null
}

/** 上一頁的第一步。第 1 步沒有上一個。 */
export function previousOf(step: number): number | null {
  const page = pageOf(step)
  return page > STEP.admin ? pageOf(page - 1) : null
}

/** 這一頁做完了：後端已經過了它。「前往下一個泊位」只在這時候有。 */
export function advanced(step: number, current: number): boolean {
  return pageOf(current) > pageOf(step)
}

/**
 * 在回頭看：畫面停在比「剛做完的那一頁」更前面的地方。剛做完、停在結果上的那一頁不算——
 * 它的下一頁就是後端目前那一頁，「前往下一個泊位」就是回去的路。
 */
export function straying(step: number, current: number): boolean {
  const next = nextOf(step)
  return next !== null && pageOf(next) < pageOf(current)
}

/** 泊位板與前置列上點得到的步驟：走過的與目前的。 */
export function reachable(step: number, current: number): boolean {
  return pageOf(step) <= pageOf(current)
}

/** 這一步屬於哪一個泊位。前置的兩步與完成頁不屬於任何泊位。 */
export function berthOf(step: number): BerthSlot | null {
  const page = pageOf(step)
  const slots = Object.keys(BERTH_STEP) as BerthSlot[]
  return slots.find((slot) => BERTH_STEP[slot] === page) ?? null
}

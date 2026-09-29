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
 * - 去後端目前那一步（或更後面）就是解除覆寫，所以回頭之後永遠走得回來。
 *
 * 一步一頁（票 06e 把索引站與 TMDB 拆成兩個泊位之後）：「頁」與「步」是同一個號碼。
 */

/**
 * plan §9.3 的六頁（M4 票 15）：Jellyfin（擁有者）→ qBittorrent → 媒體庫與路徑 → Prowlarr 與索引站
 * → TMDB → 完成。媒體庫與路徑排在 qBittorrent 之後（票 06d）。沒有偵測那一步：來源由使用者在各服務
 * 那一頁選。
 */
export const STEP = {
  jellyfin: 1,
  qbittorrent: 2,
  routes: 3,
  indexer: 4,
  tmdb: 5,
  complete: 6,
} as const

export const TOTAL_STEPS = STEP.complete

/** 每個泊位是哪一步。泊位板點下去就去這一步。 */
export const BERTH_STEP = {
  jellyfin: STEP.jellyfin,
  qbittorrent: STEP.qbittorrent,
  library: STEP.routes,
  prowlarr: STEP.indexer,
  tmdb: STEP.tmdb,
} as const satisfies Record<BerthSlot, number>

/** 畫面上是哪一步。覆寫只能往回：後端退回去了的話，還沒到的那一步不能看。 */
export function shownStep(current: number, pinned: number | null): number {
  return pinned !== null && pinned <= current ? pinned : current
}

/** 去某一步之後的覆寫。去後端目前那一步或更後面就是解除覆寫——不必記得另一顆「回到目前」。 */
export function go(target: number, current: number): number | null {
  return target >= current ? null : target
}

/** 下一步。完成頁沒有下一個。 */
export function nextOf(step: number): number | null {
  return step < STEP.complete ? step + 1 : null
}

/** 上一步。Jellyfin 那一頁沒有上一個。 */
export function previousOf(step: number): number | null {
  return step > STEP.jellyfin ? step - 1 : null
}

/** 這一步做完了：後端已經過了它。「前往下一個泊位」只在這時候有。 */
export function advanced(step: number, current: number): boolean {
  return current > step
}

/**
 * 在回頭看：畫面停在比「剛做完的那一步」更前面的地方。剛做完、停在結果上的那一步不算——
 * 它的下一步就是後端目前那一步，「前往下一個泊位」就是回去的路。
 */
export function straying(step: number, current: number): boolean {
  const next = nextOf(step)
  return next !== null && next < current
}

/** 泊位板上點得到的頁：走過的與目前的。 */
export function reachable(step: number, current: number): boolean {
  return step <= current
}

/** 這一頁屬於哪一個泊位。只有完成頁不在板上。 */
export function berthOf(step: number): BerthSlot | null {
  const slots = Object.keys(BERTH_STEP) as BerthSlot[]
  return slots.find((slot) => BERTH_STEP[slot] === step) ?? null
}

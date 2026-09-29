import { describe, expect, it } from 'vitest'

import {
  BERTH_STEP,
  STEP,
  TOTAL_STEPS,
  advanced,
  berthOf,
  go,
  nextOf,
  previousOf,
  reachable,
  shownStep,
  straying,
} from './navigation'

describe('頁序（plan §9.3，M4 票 15）', () => {
  /** Jellyfin → qBittorrent → 媒體庫與路徑 → Prowlarr 與索引站 → TMDB → 完成；沒有偵測那一步。 */
  it('六頁，Jellyfin 是第一頁，完成是最後一頁', () => {
    expect(STEP).toEqual({
      jellyfin: 1,
      qbittorrent: 2,
      routes: 3,
      indexer: 4,
      tmdb: 5,
      complete: 6,
    })
    expect(TOTAL_STEPS).toBe(6)
  })
})

describe('畫面停在哪一頁', () => {
  it('沒有覆寫時跟著後端的頁', () => {
    expect(shownStep(STEP.routes, null)).toBe(STEP.routes)
  })

  it('覆寫到走過的頁就停在那裡', () => {
    expect(shownStep(STEP.routes, STEP.jellyfin)).toBe(STEP.jellyfin)
  })

  /** 後端退回去了（例如換了一台 qBittorrent，那一頁要重做）：還沒到的那一頁不能看。 */
  it('覆寫到比後端還前面的頁不算數', () => {
    expect(shownStep(STEP.qbittorrent, STEP.indexer)).toBe(STEP.qbittorrent)
  })
})

describe('前往與回頭', () => {
  it('上一個：每一頁都回到前一頁，Jellyfin 沒有上一個', () => {
    expect(previousOf(STEP.jellyfin)).toBeNull()
    expect(previousOf(STEP.qbittorrent)).toBe(STEP.jellyfin)
    expect(previousOf(STEP.routes)).toBe(STEP.qbittorrent)
    expect(previousOf(STEP.indexer)).toBe(STEP.routes)
    expect(previousOf(STEP.tmdb)).toBe(STEP.indexer)
    expect(previousOf(STEP.complete)).toBe(STEP.tmdb)
  })

  it('下一個：一頁接一頁，完成頁沒有下一個', () => {
    expect(nextOf(STEP.jellyfin)).toBe(STEP.qbittorrent)
    expect(nextOf(STEP.qbittorrent)).toBe(STEP.routes)
    expect(nextOf(STEP.routes)).toBe(STEP.indexer)
    expect(nextOf(STEP.indexer)).toBe(STEP.tmdb)
    expect(nextOf(STEP.tmdb)).toBe(STEP.complete)
    expect(nextOf(STEP.complete)).toBeNull()
  })

  it('去後端目前那一頁（或更後面）就是解除覆寫', () => {
    expect(go(STEP.routes, STEP.routes)).toBeNull()
    expect(go(STEP.complete, STEP.routes)).toBeNull()
    expect(go(STEP.tmdb, STEP.tmdb)).toBeNull()
  })

  it('去走過的頁是覆寫', () => {
    expect(go(STEP.jellyfin, STEP.routes)).toBe(STEP.jellyfin)
    expect(go(STEP.indexer, STEP.tmdb)).toBe(STEP.indexer)
  })

  /**
   * 票 06d 的 bug：走完過的人回到前面再按「前往下一個」，落到的是最後一頁——那顆鍵做的是
   * 解除覆寫。現在「前往」是去下一頁，只有下一頁就是後端目前那一頁時才解除。
   */
  it('從 Jellyfin 頁前往下一個，落在 qBittorrent，不是後端目前那一頁', () => {
    expect(shownStep(STEP.complete, go(nextOf(STEP.jellyfin)!, STEP.complete))).toBe(
      STEP.qbittorrent,
    )
  })

  /** 票 06d 的 bug：完成頁回媒體庫路徑之後出不去。回頭之後前往下一個，一路走得回來。 */
  it('從完成頁回頭，一路前往下一個走得回完成頁', () => {
    const current = STEP.complete
    let pinned = go(previousOf(current)!, current)
    const walked: number[] = []
    while (pinned !== null) {
      walked.push(shownStep(current, pinned))
      pinned = go(nextOf(shownStep(current, pinned))!, current)
    }
    expect(walked).toEqual([STEP.tmdb])
    expect(shownStep(current, pinned)).toBe(STEP.complete)
  })
})

describe('做完了沒、回頭看了沒', () => {
  it('後端已經過了這一頁，才算這一頁做完', () => {
    expect(advanced(STEP.jellyfin, STEP.jellyfin)).toBe(false)
    expect(advanced(STEP.jellyfin, STEP.qbittorrent)).toBe(true)
    expect(advanced(STEP.indexer, STEP.tmdb)).toBe(true)
    expect(advanced(STEP.tmdb, STEP.tmdb)).toBe(false)
  })

  /**
   * 剛做完、停在結果上的那一頁不算回頭看：它的下一頁就是後端目前那一頁，
   * 「前往下一個泊位」與「回到目前這一步」是同一件事，不必兩顆鍵。
   */
  it('停在剛做完的結果上不是回頭看', () => {
    expect(straying(STEP.jellyfin, STEP.qbittorrent)).toBe(false)
    expect(straying(STEP.tmdb, STEP.complete)).toBe(false)
  })

  it('比那更前面才是回頭看', () => {
    expect(straying(STEP.jellyfin, STEP.routes)).toBe(true)
    expect(straying(STEP.qbittorrent, STEP.complete)).toBe(true)
    expect(straying(STEP.indexer, STEP.complete)).toBe(true)
  })
})

describe('點得到哪幾頁', () => {
  it('走過的與目前的點得到，還沒到的點不到', () => {
    expect(reachable(STEP.jellyfin, STEP.routes)).toBe(true)
    expect(reachable(STEP.routes, STEP.routes)).toBe(true)
    expect(reachable(STEP.indexer, STEP.routes)).toBe(false)
  })

  it('TMDB 那一格要 Prowlarr 那一頁有結論之後才點得到', () => {
    expect(reachable(STEP.indexer, STEP.tmdb)).toBe(true)
    expect(reachable(STEP.tmdb, STEP.indexer)).toBe(false)
  })
})

describe('頁與泊位', () => {
  /** 泊位板五格、沒有前置列：每一頁（除了完成）就是板上的一格（M4 票 15）。 */
  it('五個泊位各對到一頁，只有完成頁不在板上', () => {
    expect(BERTH_STEP).toEqual({
      jellyfin: STEP.jellyfin,
      qbittorrent: STEP.qbittorrent,
      library: STEP.routes,
      prowlarr: STEP.indexer,
      tmdb: STEP.tmdb,
    })
    expect(berthOf(STEP.jellyfin)).toBe('jellyfin')
    expect(berthOf(STEP.tmdb)).toBe('tmdb')
    expect(berthOf(STEP.indexer)).toBe('prowlarr')
    expect(berthOf(STEP.complete)).toBeNull()
  })
})

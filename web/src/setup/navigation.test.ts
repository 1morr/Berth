import { describe, expect, it } from 'vitest'

import {
  BERTH_STEP,
  STEP,
  advanced,
  berthOf,
  go,
  nextOf,
  previousOf,
  reachable,
  shownStep,
  straying,
} from './navigation'

describe('畫面停在哪一步', () => {
  it('沒有覆寫時跟著後端的步驟', () => {
    expect(shownStep(STEP.routes, null)).toBe(STEP.routes)
  })

  it('覆寫到走過的步驟就停在那裡', () => {
    expect(shownStep(STEP.routes, STEP.jellyfin)).toBe(STEP.jellyfin)
  })

  /** 後端退回去了（例如偵測結果又變回等待）：還沒到的那一步不能看。 */
  it('覆寫到比後端還前面的步驟不算數', () => {
    expect(shownStep(STEP.detect, STEP.qbittorrent)).toBe(STEP.detect)
  })
})

describe('前往與回頭', () => {
  it('上一個：每一步都回到前一頁，第 1 步沒有上一個', () => {
    expect(previousOf(STEP.admin)).toBeNull()
    expect(previousOf(STEP.detect)).toBe(STEP.admin)
    expect(previousOf(STEP.jellyfin)).toBe(STEP.detect)
    expect(previousOf(STEP.routes)).toBe(STEP.qbittorrent)
    expect(previousOf(STEP.indexer)).toBe(STEP.routes)
    // 索引站與 TMDB 各是一個泊位（票 06e），TMDB 的上一個就是索引站。
    expect(previousOf(STEP.tmdb)).toBe(STEP.indexer)
    expect(previousOf(STEP.complete)).toBe(STEP.tmdb)
  })

  it('下一個：一步一頁，完成頁沒有下一個', () => {
    expect(nextOf(STEP.detect)).toBe(STEP.jellyfin)
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

  it('去走過的步驟是覆寫', () => {
    expect(go(STEP.jellyfin, STEP.routes)).toBe(STEP.jellyfin)
    // 拆開之後索引站在 TMDB 之前，是走過的那一頁。
    expect(go(STEP.indexer, STEP.tmdb)).toBe(STEP.indexer)
  })

  /**
   * 票 06d 的 bug：走完過的人按「重新探測」再按「前往泊位 1」，落到的是最後一步——
   * 那顆鍵做的是解除覆寫。現在「前往」是去下一頁，只有下一頁就是後端目前那一頁時才解除。
   */
  it('從第 2 步前往下一個，落在泊位 1，不是後端目前那一步', () => {
    expect(shownStep(STEP.complete, go(nextOf(STEP.detect)!, STEP.complete))).toBe(STEP.jellyfin)
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
    // 索引站做完、TMDB 還沒：索引站那一格做完了（票 06e 拆開之前它們是同一頁）。
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
    expect(straying(STEP.detect, STEP.complete)).toBe(true)
    expect(straying(STEP.indexer, STEP.complete)).toBe(true)
  })
})

describe('點得到哪幾步', () => {
  it('走過的與目前的點得到，還沒到的點不到', () => {
    expect(reachable(STEP.jellyfin, STEP.routes)).toBe(true)
    expect(reachable(STEP.routes, STEP.routes)).toBe(true)
    expect(reachable(STEP.indexer, STEP.routes)).toBe(false)
  })

  it('TMDB 那一格要索引站有結論之後才點得到', () => {
    expect(reachable(STEP.indexer, STEP.tmdb)).toBe(true)
    expect(reachable(STEP.tmdb, STEP.indexer)).toBe(false)
  })
})

describe('步驟與泊位', () => {
  /** 票 06e：板變 5 格，每一格一個服務、一步。 */
  it('五個泊位各對到一步，前置兩步與完成頁不屬於任何泊位', () => {
    expect(BERTH_STEP).toEqual({
      jellyfin: STEP.jellyfin,
      qbittorrent: STEP.qbittorrent,
      library: STEP.routes,
      prowlarr: STEP.indexer,
      tmdb: STEP.tmdb,
    })
    expect(berthOf(STEP.tmdb)).toBe('tmdb')
    expect(berthOf(STEP.indexer)).toBe('prowlarr')
    expect([STEP.admin, STEP.detect, STEP.complete].map(berthOf)).toEqual([null, null, null])
  })
})

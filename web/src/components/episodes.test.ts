import { describe, expect, it } from 'vitest'

import { formatCoverage } from './episodes'

function span(episode_start: number | null, episode_end: number | null = null) {
  return { episode_start, episode_end }
}

describe('一組檔案蓋到的集數（M1.5 票 09）', () => {
  it('連續的寫成一段，季代號與集號之間空一格——不是 Jellyfin 多集檔的 `S01E01-E28`', () => {
    const items = Array.from({ length: 28 }, (_, index) => span(index + 1))

    expect(formatCoverage(1, items)).toBe('S01 E01–E28')
  })

  it('斷開的逗號分開，只有一集的那一段不寫範圍', () => {
    expect(formatCoverage(1, [span(1), span(2), span(3), span(5), span(7), span(8)])).toBe(
      'S01 E01–E03, E05, E07–E08',
    )
  })

  it('多集檔算它蓋到的每一集；同一集的第二個檔案（字幕、另一個版本）不重複算', () => {
    expect(formatCoverage(0, [span(1, 2), span(3), span(1), span(3)])).toBe('S00 E01–E03')
  })

  it('順序不影響結果', () => {
    expect(formatCoverage(2, [span(4), span(2), span(3)])).toBe('S02 E02–E04')
  })

  it('有季沒有集的只寫季；沒有季的（略過、對不到）是空字串', () => {
    expect(formatCoverage(1, [span(null)])).toBe('S01')
    expect(formatCoverage(null, [span(3)])).toBe('')
  })
})

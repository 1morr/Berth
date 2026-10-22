import { describe, expect, it } from 'vitest'

import { countEpisodes, describeSpans } from './spans'

describe('週報的季集範圍', () => {
  it('同一季接著寫集，換季才寫季', () => {
    expect(
      describeSpans([
        [1, 1, 3],
        [1, 5, 5],
        [2, 1, 1],
      ]),
    ).toBe('S01E01–E03, E05, S02E01')
  })

  it('沒有任何一段是空字串', () => {
    expect(describeSpans([])).toBe('')
  })

  it('集數照每一段的長度加總', () => {
    expect(
      countEpisodes([
        [1, 1, 3],
        [1, 5, 5],
        [2, 1, 1],
      ]),
    ).toBe(5)
  })
})

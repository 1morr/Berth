import { describe, expect, it } from 'vitest'

import type { Media } from '../api/media'
import { preselect } from './preselect'

function detail(kind: 'tv' | 'movie', ids: number[], last: number | null = null): Media {
  return {
    kind,
    default_route_id: last,
    routes: ids.map((id) => ({ id, name: `R${id}` })),
  } as Media
}

describe('preselect（M4 票 105）', () => {
  it('先看長出它的 Feed 那一種的 Route', () => {
    expect(preselect(detail('tv', [3, 4], 4), { tv: 3, movie: 5 })).toBe(3)
    expect(preselect(detail('movie', [5, 6]), { tv: 3, movie: 6 })).toBe(6)
  })

  it('Feed 的那一條收不下這部作品時不算，退回上次用的、再退回唯一的', () => {
    expect(preselect(detail('tv', [3, 4], 4), { tv: 9, movie: null })).toBe(4)
    expect(preselect(detail('movie', [5]), { tv: 3, movie: null })).toBe(5)
  })

  it('都不成立時留給人選', () => {
    expect(preselect(detail('tv', [3, 4]), { tv: null, movie: null })).toBeNull()
    expect(preselect(detail('tv', [3, 4]))).toBeNull()
    expect(preselect(undefined, { tv: 3, movie: null })).toBeNull()
  })
})

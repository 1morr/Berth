import { describe, expect, it } from 'vitest'

import type { Feed } from '../api/rss'
import type { RouteView } from '../api/schemas'
import { bindsNow, complete, prefilled, routesFor, routesOf, unsetKinds } from './feedRoutes'

function route(id: number, kind: 'tvshows' | 'movies', enabled = true): RouteView {
  return { id, name: `R${id}`, collection_type: kind, enabled } as RouteView
}

function feed(overrides: Partial<Feed> = {}): Feed {
  return {
    tv_route_id: null,
    movie_route_id: null,
    route_kinds: ['tv', 'movie'],
    awaiting_route: { tv: 2, movie: 1 },
    ...overrides,
  } as Feed
}

const ROUTES = [
  route(3, 'tvshows'),
  route(4, 'tvshows'),
  route(5, 'movies'),
  route(6, 'movies', false),
]

describe('Feed 的兩條 Route（M4 票 105）', () => {
  it('停用的不給選', () => {
    expect(routesFor(ROUTES, 'movie').map((row) => row.id)).toEqual([5])
  })

  it('只有一條時預填它，兩條以上留給人選', () => {
    expect(prefilled(ROUTES)).toEqual({ tv: null, movie: 5 })
    expect(prefilled([])).toEqual({ tv: null, movie: null })
  })

  it('空著而那一種有 Route 的那一格要人選', () => {
    expect(unsetKinds(feed({ movie_route_id: 5 }), ROUTES)).toEqual(['tv'])
    expect(unsetKinds(feed({ tv_route_id: 3, movie_route_id: 5 }), ROUTES)).toEqual([])
    expect(unsetKinds(feed(), [route(3, 'tvshows')])).toEqual(['tv'])
  })

  it('從作品頁訂閱建的只看它用得到的那一種（後端的 route_kinds）', () => {
    const series = feed({ tv_route_id: 3, route_kinds: ['tv'] })
    expect(unsetKinds(series, ROUTES)).toEqual([])
    expect(bindsNow(series, ROUTES)).toBe(2)
    expect(complete({ tv: 3, movie: null }, ROUTES, series.route_kinds)).toBe(true)
  })

  it('指著停用的那一條也算空著：自動綁定不看它', () => {
    expect(unsetKinds(feed({ tv_route_id: 3, movie_route_id: 6 }), ROUTES)).toEqual(['movie'])
    expect(routesOf(feed({ tv_route_id: 3, movie_route_id: 6 }), ROUTES)).toEqual({
      tv: 3,
      movie: null,
    })
  })

  it('那一種沒有 Route 時那一格不必選', () => {
    expect(complete({ tv: 3, movie: null }, [route(3, 'tvshows')])).toBe(true)
    expect(complete({ tv: null, movie: 5 }, ROUTES)).toBe(false)
  })

  it('會當場綁上幾部：只算有 Route 的那幾種', () => {
    expect(bindsNow(feed(), [route(3, 'tvshows')])).toBe(2)
    expect(bindsNow(feed(), ROUTES)).toBe(3)
  })
})

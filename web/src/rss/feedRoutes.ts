import type { Feed, KindRoutes } from '../api/rss'
import type { MediaKind, RouteView } from '../api/schemas'

/**
 * Feed 的兩條 Route（M4 票 105）：劇集、電影各一條，照 Sonarr Import List 的 Root Folder 必填。
 *
 * 那一種有啟用中的 Route 才有那一格（後端零條時不收、存 `null`）；只有一條時預填它。
 */
export const KINDS: readonly MediaKind[] = ['tv', 'movie']

const COLLECTION: Record<MediaKind, RouteView['collection_type']> = {
  tv: 'tvshows',
  movie: 'movies',
}

/** 收得下這一種、啟用中的 Route。停用的那一條自動綁定不看，也不給選。 */
export function routesFor(routes: RouteView[], kind: MediaKind): RouteView[] {
  return routes.filter((row) => row.enabled && row.collection_type === COLLECTION[kind])
}

/** 新增表單的初值：那一種只有一條時就是它，否則留給人選。 */
export function prefilled(routes: RouteView[]): KindRoutes {
  const only = (kind: MediaKind) => {
    const rows = routesFor(routes, kind)
    return rows.length === 1 ? rows[0].id : null
  }
  return { tv: only('tv'), movie: only('movie') }
}

/**
 * Feed 的兩格，只算還收得下那一種的啟用中 Route：那條被停用了，自動綁定也不看它（後端退回
 * 「只有一條」），畫面當它空著——要人重選，下拉也才有那個值。
 */
export function routesOf(feed: Feed, routes: RouteView[]): KindRoutes {
  const live = (kind: MediaKind, id: number | null) =>
    routesFor(routes, kind).some((row) => row.id === id) ? id : null
  return { tv: live('tv', feed.tv_route_id), movie: live('movie', feed.movie_route_id) }
}

/** 要人選的那幾種：那一種有啟用中的 Route，這一格卻空著或指著停用的那條（票 105 之前加的 Feed）。 */
export function unsetKinds(feed: Feed, routes: RouteView[]): MediaKind[] {
  const own = routesOf(feed, routes)
  return KINDS.filter((kind) => own[kind] === null && routesFor(routes, kind).length > 0)
}

/** 那幾格都選好了沒：有 Route 的那一種要有值。 */
export function complete(chosen: KindRoutes, routes: RouteView[]): boolean {
  return KINDS.every((kind) => chosen[kind] !== null || routesFor(routes, kind).length === 0)
}

/**
 * 存下之後會當場綁上幾部：停在 `route_ambiguous`、而那一種有 Route 的。有 Route 的每一種都得選了才
 * 存得下（`complete`），所以還沒選時說的也是存下那一刻的數字。
 */
export function bindsNow(feed: Feed, routes: RouteView[]): number {
  return KINDS.reduce(
    (sum, kind) => sum + (routesFor(routes, kind).length === 0 ? 0 : feed.awaiting_route[kind]),
    0,
  )
}

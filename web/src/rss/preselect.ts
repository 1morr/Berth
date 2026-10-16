import type { Media } from '../api/media'
import type { KindRoutes } from '../api/rss'

/**
 * 詳情一到就預選，依序：長出這個 RSS Series 的 Feed 那一種的 Route（M4 票 105）、上次用的 Route、
 * 唯一的那一條。都不成立時留給人選。每一條都要是這部作品收得下的（`detail.routes`）。
 */
export function preselect(detail: Media | undefined, feed?: KindRoutes): number | null {
  if (!detail) return null
  const choices = detail.routes.map((row) => row.id)
  const fromFeed = feed?.[detail.kind] ?? null
  if (fromFeed !== null && choices.includes(fromFeed)) return fromFeed
  if (detail.default_route_id !== null && choices.includes(detail.default_route_id))
    return detail.default_route_id
  return choices.length === 1 ? choices[0] : null
}

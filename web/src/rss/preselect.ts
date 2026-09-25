import type { Media } from '../api/media'

/** 詳情一到就預選：上次用的 Route，沒有就是唯一的那一條。兩條以上而從沒送過單時留給人選。 */
export function preselect(detail: Media | undefined): number | null {
  if (!detail) return null
  const choices = detail.routes.map((row) => row.id)
  if (detail.default_route_id !== null && choices.includes(detail.default_route_id))
    return detail.default_route_id
  return choices.length === 1 ? choices[0] : null
}

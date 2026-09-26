import type { JobEvent } from '../api/jobs'

/**
 * 認得的事件型別（`domain.EventType`）。
 *
 * **一份清單，兩個用途**：`FACTS` 的鍵型別由它產生，所以少寫一個 renderer 會在 `tsc` 就紅；
 * `label()` 也讀它，所以「有沒有那一句顯示名」與「畫不畫得出那幾格」不會分岔。
 * 票 11 加 `plan_generated` 時，型別檢查會直接指到還沒補的那一格。
 */
export const EVENT_TYPES = [
  'created',
  'submitted',
  'submit_failed',
  'retried',
  'metadata_received',
  'progress',
  'stalled',
  'completed',
  'issue_detected',
  'preplan',
  'plan_generated',
  'review_required',
  'review_decided',
  'linked',
  'link_failed',
  'jellyfin_scan_requested',
  'jellyfin_item_resolved',
  'jellyfin_request_failed',
  'deleted',
  'audit_confirmed',
  'audit_undone',
  'rematched',
  'duplicate_skipped',
  'duplicate_decided',
  'recovered',
  'round_failed',
  'series_confirmed',
] as const

export type KnownEvent = (typeof EVENT_TYPES)[number]

/**
 * Plan 歷史（M2 票 12、`.scratch/m2/job-detail-shape.md`）：一筆 Job 只有一份現行 Plan，重新規劃整份
 * 換掉，所以「這份決定被誰、何時、怎麼改過」只在時間線上。這十種就是那些事件；畫法仍是 `JobTimeline`。
 * `series_confirmed` 是 M4 票 11 加的：系統確認第一批時清掉的正是這一份的 audit。
 */
const PLAN_EVENTS: ReadonlySet<string> = new Set<KnownEvent>([
  'preplan',
  'plan_generated',
  'review_required',
  'review_decided',
  'audit_confirmed',
  'audit_undone',
  'rematched',
  'duplicate_skipped',
  'duplicate_decided',
  'series_confirmed',
])

/** 時間線裡屬於 Plan 歷史的那幾筆，順序不動。 */
export function planHistory(events: readonly JobEvent[]): JobEvent[] {
  return events.filter((event) => PLAN_EVENTS.has(event.type))
}

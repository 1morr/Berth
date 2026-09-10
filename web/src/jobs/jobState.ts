import type { Job, JobState } from '../api/jobs'
import type { PlanItem } from '../api/plans'
import type { Signal } from '../components/signal'

/**
 * Job 狀態的讀法（`.scratch/m1/jobs-shape.md` §7）。
 *
 * 純函式、沒有 JSX：列上的色塊、就地展開區與 `aria-live` 的宣告說的是同一件事，
 * 而同一件事在三個元件裡各算一次遲早會分岔。
 */

/**
 * 十六個狀態 → 四個信號色（The One Meaning Rule）。
 *
 * **一次映射完**，不是「這一票只做三個」：`JobState` 是同一個封閉集合（`domain/enums.py`），
 * 分兩批做的話票 10 接上 poller 那天畫面會在某個狀態上落回一個沒有顏色的格子。
 *
 * 三條規則決定了誰是什麼色：
 * - `blocked` **只代表阻擋**——在你動手之前走不下去。所以 `stalled`（做種變多就會自己恢復）
 *   不是紅的，`client_removed`（torrent 不在客戶端了，但檔案可能還在）也不是。
 * - `assigned` 是「現在需要你」：`review` 等一個決定，`stalled` 等你去看看它為什麼不動。
 * - `working` 只表示「還沒有結論」，不表示成功。
 */
export const JOB_SIGNAL: Record<JobState, Signal> = {
  requested: 'working',
  submitted: 'secured',
  submit_failed: 'blocked',
  metadata_ready: 'secured',
  downloading: 'working',
  stalled: 'assigned',
  missing_files: 'blocked',
  client_error: 'blocked',
  client_removed: 'neutral',
  completed: 'secured',
  planning: 'working',
  review: 'assigned',
  importing: 'working',
  imported: 'secured',
  import_failed: 'blocked',
  removed: 'neutral',
}

/**
 * 進度那一格。票 10 起它是真的值——poller 每一輪把 qBittorrent 報的 `progress` 寫回來，
 * SSE 讓這一列自己重問（`api/events.ts`）。
 *
 * **0 仍然是 `—` 而不是 `0%`**：送單到拿到第一批資料之間那一段，qBittorrent 還沒有話說，
 * 而 `0%` 讀起來像「量過了，是零」（票 09 的同一條：沒有值就說沒有值）。
 */
export function formatProgress(job: Job, locale: string): string {
  if (job.progress <= 0) return '—'
  return formatPercent(job.progress, locale)
}

/** 0.0–1.0 → `42%`。列上與時間線用同一支——同一個數字不該有兩種樣子。 */
export function formatPercent(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 }).format(value)
}

/**
 * hash 的前 12 字。認人夠用，而整串 40 字會把窄版那一行擠爆。
 *
 * 完整的那一串在展開區的 `CopyLine` 裡——它是使用者拿去 qBittorrent 介面上比對的東西，
 * 所以複製得到整串才算數。
 */
export function shortHash(hash: string): string {
  return hash.slice(0, 12)
}

/**
 * `S01E01` / `S01E01-E02`（Jellyfin 認得的寫法，brief §6.6）。
 *
 * **不是 i18n 字串**：它與檔名裡的那一段是同一個東西，翻譯它等於讓畫面上的季集與磁碟上的
 * 檔名對不起來（The Machine String Rule 的同一個道理）。電影沒有季集，回空字串。
 */
export function formatEpisode(item: PlanItem): string {
  if (item.season === null || item.episode_start === null) return ''
  const season = String(item.season).padStart(2, '0')
  const start = String(item.episode_start).padStart(2, '0')
  const end =
    item.episode_end && item.episode_end !== item.episode_start
      ? `-E${String(item.episode_end).padStart(2, '0')}`
      : ''
  return `S${season}E${start}${end}`
}

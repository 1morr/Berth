import type { Job, JobState } from '../api/jobs'
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
 * 進度那一格。**這一票永遠是 `—`**：`progress` 要等票 10 的 poller 才會動
 * （shape brief §5）。欄位現在就在，值回來時同一個位置開始跳數字，版面不重排。
 */
export function formatProgress(job: Job, locale: string): string {
  if (job.progress <= 0) return '—'
  return new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 }).format(
    job.progress,
  )
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

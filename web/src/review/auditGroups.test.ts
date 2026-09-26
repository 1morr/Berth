import { describe, expect, it } from 'vitest'

import type { AuditReviewRow, DuplicateReviewRow, ReviewRow } from '../api/review'
import { groupAudits, type ReviewEntry } from './auditGroups'

const JOB_A = 'a'.repeat(40)
const JOB_B = 'b'.repeat(40)

type Series = NonNullable<AuditReviewRow['series']>

function series(overrides: Partial<Series> = {}): Series {
  return {
    id: 3,
    name: '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 - 01',
    group: '喵萌奶茶屋&LoliHouse',
    confirmed: false,
    season: null,
    episode_offset: null,
    ask: null,
    ...overrides,
  }
}

function audit(ref: number, overrides: Partial<AuditReviewRow> = {}): AuditReviewRow {
  return {
    kind: 'audit',
    ref,
    // 與後端同一條（`review._audit_row`）：還沒確認的 RSS Series 送的就是第一批。
    reason: {
      code:
        overrides.series && !overrides.series.confirmed ? 'first_batch' : 'medium_auto_imported',
      params: {},
    },
    actions: ['confirm', 'undo'],
    at: '2026-09-22T04:00:00Z',
    media_id: 'tv:1',
    title: '作品',
    title_en: 'Work',
    job_hash: JOB_A,
    job_name: 'job',
    path: `/library/${ref}.mkv`,
    source_path: `/complete/${ref}.mkv`,
    action: 'import',
    season: 1,
    episode_start: ref,
    episode_end: null,
    reasons: [],
    series: null,
    ...overrides,
  }
}

function duplicate(ref: number): DuplicateReviewRow {
  return {
    kind: 'duplicate',
    ref,
    reason: { code: 'same_version', params: {} },
    actions: ['replace', 'keep_both', 'skip'],
    at: '2026-09-22T05:00:00Z',
    media_id: 'tv:1',
    title: '作品',
    title_en: 'Work',
    job_hash: JOB_B,
    job_name: 'other',
    path: '/complete/dup.mkv',
    season: 1,
    episode_start: 1,
    episode_end: null,
    known_path: '/library/dup.mkv',
    known_season: 1,
    known_episode_start: 1,
    known_episode_end: null,
  }
}

/** 每一格的樣子：單列是它的 ref，一組是鍵與成員的 ref。 */
function shape(entries: readonly ReviewEntry[]) {
  return entries.map((entry) =>
    entry.kind === 'row' ? entry.row.ref : { key: entry.key, refs: entry.rows.map((r) => r.ref) },
  )
}

describe('audit 的分組', () => {
  it('同一個 Job 收成一組，位置是第一列出現的地方', () => {
    const rows: ReviewRow[] = [audit(1), duplicate(40), audit(2), audit(3, { job_hash: JOB_B })]

    expect(shape(groupAudits(rows))).toEqual([{ key: `job:${JOB_A}`, refs: [1, 2] }, 40, 3])
  })

  // 補舊集一次送 12 筆下載（M3 票 13）：一集一個 Job，以 Job 分組等於不分。
  it('有 RSS Series 的以 Series 分組，先於 Job', () => {
    const rows: ReviewRow[] = [
      audit(1, { series: series() }),
      audit(2, { job_hash: JOB_B, series: series() }),
      audit(3, { series: series({ id: 4 }) }),
      audit(4),
    ]

    expect(shape(groupAudits(rows))).toEqual([
      { key: 'series:3', refs: [1, 2] },
      // 同一個 Job 的另一列落在別的 Series：不跟 Job 那一組併。
      { key: 'series:4', refs: [3] },
      4,
    ])
  })

  it('還沒確認的 Series 只有一列時仍是一組：組的「全部確認」會確認整個 Series', () => {
    const rows: ReviewRow[] = [audit(1, { series: series() })]

    expect(shape(groupAudits(rows))).toEqual([{ key: 'series:3', refs: [1] }])
  })

  it('確認過的 Series 只有一列時就是一列，同 Job', () => {
    const rows: ReviewRow[] = [audit(1, { series: series({ confirmed: true }) }), audit(2)]

    expect(shape(groupAudits(rows))).toEqual([1, 2])
  })

  it('沒有 Job 也沒有 Series 的不分組', () => {
    const rows: ReviewRow[] = [audit(1, { job_hash: '' }), audit(2, { job_hash: '' })]

    expect(shape(groupAudits(rows))).toEqual([1, 2])
  })
})

import { describe, expect, it } from 'vitest'

import type { JobEvent } from '../api/jobs'
import { planHistory } from './eventTypes'

function event(id: number, type: string): JobEvent {
  return { id, type, actor: 'system', payload: {}, created_at: '2026-09-10T12:00:00Z' }
}

describe('計劃歷史（M2 票 12）', () => {
  it('只留下那份決定怎麼變成現在這樣的九種事件，順序不動', () => {
    const types = [
      'created',
      'preplan',
      'submitted',
      'plan_generated',
      'review_required',
      'review_decided',
      'linked',
      'audit_confirmed',
      'audit_undone',
      'rematched',
      'duplicate_skipped',
      'duplicate_decided',
      'deleted',
    ]
    const rows = types.map((type, index) => event(index + 1, type))

    expect(planHistory(rows).map((row) => row.type)).toEqual([
      'preplan',
      'plan_generated',
      'review_required',
      'review_decided',
      'audit_confirmed',
      'audit_undone',
      'rematched',
      'duplicate_skipped',
      'duplicate_decided',
    ])
  })
})

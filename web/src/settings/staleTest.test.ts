import { describe, expect, it } from 'vitest'

import type { ServiceHealth } from '../api/health'
import { chosen, healthDetail } from '../test/fixtures'
import { staleTest } from './staleTest'

const TESTED = '2026-09-08T12:00:00Z'
const LATER = '2026-09-08T12:05:00Z'
const EARLIER = '2026-09-08T11:55:00Z'

function health(overrides: Partial<ServiceHealth>): ServiceHealth {
  return { ...healthDetail().services[0], ...overrides }
}

describe('staleTest（M4 票 61）', () => {
  it('測試通過之後健康檢查連不上：過時', () => {
    expect(
      staleTest(chosen({ checked_at: TESTED }), health({ status: 'failed', checked_at: LATER })),
    ).toBe(true)
  })

  it('健康那一輪比測試舊、健康是綠的、或不用它：測試那一列說的就是現況', () => {
    const service = chosen({ checked_at: TESTED })
    expect(staleTest(service, health({ status: 'failed', checked_at: EARLIER }))).toBe(false)
    expect(staleTest(service, health({ status: 'ok', checked_at: LATER }))).toBe(false)
    expect(staleTest(service, health({ status: 'failed', checked_at: LATER, unused: true }))).toBe(
      false,
    )
  })

  it('測試本身沒通過或還沒測：那一列自己就不是綠的', () => {
    const failed = health({ status: 'failed', checked_at: LATER })
    expect(staleTest(chosen({ state: 'failed', checked_at: TESTED }), failed)).toBe(false)
    expect(staleTest(chosen({ checked_at: null }), failed)).toBe(false)
    expect(staleTest(undefined, failed)).toBe(false)
  })
})

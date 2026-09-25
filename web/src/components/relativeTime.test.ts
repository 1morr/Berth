import { describe, expect, it } from 'vitest'

import { relative } from './relativeTime'

const NOW = Date.parse('2026-09-25T12:00:00Z')

function ago(seconds: number, language = 'zh-Hant'): string {
  return relative(new Date(NOW - seconds * 1000), language, NOW)
}

const DAY = 86_400

describe('relative', () => {
  it('一週之內說秒、分、時、天', () => {
    expect(ago(30)).toBe('30 秒前')
    expect(ago(120)).toBe('2 分鐘前')
    expect(ago(3 * 3600)).toBe('3 小時前')
    expect(ago(3 * DAY)).toBe('3 天前')
  })

  it('一個月之內說週', () => {
    expect(ago(21 * DAY)).toBe('3 週前')
    expect(ago(21 * DAY, 'en')).toBe('3 weeks ago')
  })

  // M3 票 14：搜尋結果的發佈時間常常是幾個月、幾年前。
  it('一年之內說月，再久說年', () => {
    expect(ago(90 * DAY)).toBe('3 個月前')
    expect(ago(300 * DAY)).toBe('10 個月前')
    // 捨入成 12 個月的那幾週說「去年」（numeric: 'auto'），不說「12 個月前」。
    expect(ago(350 * DAY)).toBe('去年')
    expect(ago(2 * 365 * DAY)).toBe('2 年前')
    expect(ago(2 * 365 * DAY, 'en')).toBe('2 years ago')
  })
})

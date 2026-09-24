import { describe, expect, it } from 'vitest'

import { whenText } from './queueText'

describe('whenText', () => {
  // M2 票 16 的 critique：EN 介面每一列都印著「上午10:31:36」——它跟的是瀏覽器語系，不是 UI 語言。
  it('照 UI 的語言寫，不照瀏覽器的', () => {
    const at = '2026-09-24T02:31:36Z'

    expect(whenText(at, 'en')).not.toMatch(/[上下]午/)
    expect(whenText(at, 'en')).toMatch(/AM|PM/)
    expect(whenText(at, 'zh-Hant')).toMatch(/[上下]午/)
  })

  it('認不得的原樣印出', () => {
    expect(whenText('not a date', 'en')).toBe('not a date')
  })
})

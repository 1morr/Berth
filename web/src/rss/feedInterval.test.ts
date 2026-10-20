import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { FEED_INTERVALS, intervalLabel, isFeedInterval } from './feedInterval'

describe('Feed 的輪詢間隔（M4 票 109）', () => {
  it('七個檔位由短到長，最短 15 分鐘', () => {
    expect(FEED_INTERVALS).toEqual([900, 1800, 3600, 10800, 21600, 43200, 86400])
  })

  it('檔位外的不算', () => {
    expect(isFeedInterval(900)).toBe(true)
    expect(isFeedInterval(600)).toBe(false)
  })

  it.each([
    ['zh-Hant', ['15 分鐘', '30 分鐘', '1 小時', '3 小時', '6 小時', '12 小時', '24 小時']],
    ['en', ['15 minutes', '30 minutes', '1 hour', '3 hours', '6 hours', '12 hours', '24 hours']],
  ])('%s 的說法：整點說小時', async (language, labels) => {
    const t = i18next.getFixedT(language)
    expect(FEED_INTERVALS.map((seconds) => intervalLabel(t, seconds))).toEqual(labels)
  })
})

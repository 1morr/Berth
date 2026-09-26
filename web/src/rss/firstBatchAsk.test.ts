import i18next from 'i18next'
import { afterEach, describe, expect, it } from 'vitest'

import { firstBatchAskText } from './firstBatchAsk'

const t = i18next.t.bind(i18next)

describe('第一批在問什麼（M4 票 11）', () => {
  afterEach(async () => {
    await i18next.changeLanguage('zh-Hant')
  })

  it('說出作品 × 字幕組、蓋到的集數與季集怎麼讀出來', () => {
    expect(
      firstBatchAskText(t, {
        title: 'BLACK TORCH',
        group: 'ANi',
        ask: { spans: [{ season: 1, start: 1, end: 4 }], basis: 'literal' },
      }),
    ).toBe('確認 BLACK TORCH × ANi 的季集對應：S01 E01–E04 由集號直接對應')
  })

  it('不連續的集數分段說，只有一集的不寫範圍', () => {
    expect(
      firstBatchAskText(t, {
        title: 'Re:ZERO',
        group: 'LoliHouse',
        ask: {
          spans: [
            { season: 1, start: 39, end: 40 },
            { season: 1, start: 42, end: 42 },
          ],
          basis: 'series',
        },
      }),
    ).toBe('確認 Re:ZERO × LoliHouse 的季集對應：S01 E39–E40、S01 E42 照 Series 設的季號與偏移換算')
  })

  it('讀不出字幕組時只說作品', () => {
    expect(
      firstBatchAskText(t, {
        title: 'BLACK TORCH',
        group: '',
        ask: { spans: [{ season: 2, start: 3, end: 3 }], basis: 'mixed' },
      }),
    ).toBe('確認 BLACK TORCH 的季集對應：S02 E03 讀法不只一種')
  })

  it('英文', async () => {
    await i18next.changeLanguage('en')
    expect(
      firstBatchAskText(t, {
        title: 'BLACK TORCH',
        group: 'ANi',
        ask: {
          spans: [
            { season: 1, start: 1, end: 2 },
            { season: 1, start: 4, end: 4 },
          ],
          basis: 'runs',
        },
      }),
    ).toBe(
      'Check how BLACK TORCH × ANi maps to seasons: S01 E01–E02, S01 E04 counted within a later run (the group restarted at 01)',
    )
  })
})

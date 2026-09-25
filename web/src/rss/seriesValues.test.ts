import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import { seriesCorrectedText } from './seriesValues'

const t = i18next.t.bind(i18next)

describe('套用到 RSS Series 之後的那一句（M3 票 13）', () => {
  it('說出 Series 現在的值與跟著搬了幾集', () => {
    expect(
      seriesCorrectedText(t, { season: 1, episode_offset: 12, moved: 11, replanned: 0, left: 0 }),
    ).toBe('已修正，這個 RSS Series 改成第 1 季、集號偏移 +12。 其餘 11 集跟著搬過去了。')
  })

  it('是 0 的不說，重新規劃與搬不過去的各說一句', () => {
    expect(
      seriesCorrectedText(t, { season: 2, episode_offset: -12, moved: 0, replanned: 2, left: 1 }),
    ).toBe(
      '已修正，這個 RSS Series 改成第 2 季、集號偏移 -12。 2 筆等審核的下載照新的值重新規劃了。 1 集搬不過去，留在原處等你看。',
    )
  })

  it('沒有偏移、也沒有別的集數要跟時照實說', () => {
    expect(
      seriesCorrectedText(t, { season: 1, episode_offset: null, moved: 0, replanned: 0, left: 0 }),
    ).toBe('已修正，這個 RSS Series 改成第 1 季，集號不偏移。 沒有其他還沒確認的集數要跟著改。')
  })

  it('英文照單複數', async () => {
    await i18next.changeLanguage('en')
    try {
      expect(
        seriesCorrectedText(t, { season: 1, episode_offset: 12, moved: 1, replanned: 0, left: 2 }),
      ).toBe(
        'Fixed; this RSS Series now uses season 1, episode offset +12. One other episode followed. 2 episodes could not be moved and stay where they are for you to check.',
      )
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

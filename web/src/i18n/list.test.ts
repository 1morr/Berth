import { describe, expect, it } from 'vitest'

import { formatList, sentenceGap } from './list'

describe('formatList', () => {
  it('中文全用頓號，英文名字之間不會黏在一起', () => {
    expect(formatList(['Movies', 'TV', 'Anime'], 'zh-Hant')).toBe('Movies、TV、Anime')
  })

  it('英文照 Intl.ListFormat', () => {
    expect(formatList(['Movies', 'TV', 'Anime'], 'en')).toBe('Movies, TV, and Anime')
  })
})

describe('sentenceGap', () => {
  it('中文句與句之間不留空白，英文留一格', () => {
    expect(sentenceGap('zh-Hant')).toBe('')
    expect(sentenceGap('en')).toBe(' ')
  })
})

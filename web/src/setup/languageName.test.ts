import { describe, expect, it } from 'vitest'

import { languageName } from './languageName'

describe('索引站的語言名', () => {
  it('照 UI 語言說出語言名，不是代碼', () => {
    expect(languageName('zh-TW', 'zh-Hant')).toBe('中文（台灣）')
    expect(languageName('zh-CN', 'en')).toBe('Chinese (China)')
    expect(languageName('en-US', 'en')).toBe('American English')
  })

  it('沒有代碼就沒有名字，形狀不對的代碼原樣顯示', () => {
    expect(languageName('', 'en')).toBe('')
    expect(languageName('not a code', 'en')).toBe('not a code')
  })
})

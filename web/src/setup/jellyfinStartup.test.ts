import { describe, expect, it } from 'vitest'

import { JELLYFIN_LOCALES, localeForUi, localeLabel } from './jellyfinStartup'

describe('替既有 Jellyfin 初始化時的語言與地區（M4 票 18）', () => {
  it('預設跟著 Berth 的 UI 語言', () => {
    expect(localeForUi('zh-Hant')).toEqual({
      ui_culture: 'zh-TW',
      metadata_language: 'zh-TW',
      metadata_country: 'TW',
    })
    expect(localeForUi('en')).toEqual({
      ui_culture: 'en-US',
      metadata_language: 'en',
      metadata_country: 'US',
    })
  })

  it('每一組的名字照 UI 語言，而且互不相同', () => {
    const zh = JELLYFIN_LOCALES.map((row) => localeLabel(row, 'zh-Hant'))
    expect(zh[0]).toBe('中文（台灣）')
    expect(new Set(zh).size).toBe(JELLYFIN_LOCALES.length)
    expect(localeLabel(JELLYFIN_LOCALES[4]!, 'en')).toBe('British English')
  })

  it('代碼是後端收的形狀', () => {
    for (const row of JELLYFIN_LOCALES) {
      expect(row.ui_culture).toMatch(/^[a-z]{2,3}(-[A-Za-z]{2,4})?$/)
      expect(row.metadata_language).toMatch(/^[a-z]{2,3}(-[A-Za-z]{2,4})?$/)
      expect(row.metadata_country).toMatch(/^[A-Z]{2}$/)
    }
  })
})

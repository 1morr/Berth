import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * 介面登入只有一個叫法（M4 票 103，CONTEXT.md 的 **Interface login**）：票 68 的 critique 看到套件內
 * qBittorrent 的登入叫「WebUI 登入」、Prowlarr 的叫「介面登入」，頁 2 的標題與按鈕兩個叫法並存。
 * qBittorrent 自己的選單路徑「選項 → WebUI」是它的標籤，照留。
 */

/** 舊叫法：登入或帳號前面掛著 WebUI。選單路徑「選項 → WebUI」不算。 */
const OLD_NAME = /WebUI\s*(登入|的帳號)|WebUI (login|username)/i

/** 產品原始碼與測試（不含這一檔：它自己要寫出舊叫法當樣本）。 */
const SOURCES = import.meta.glob<string>(['../**/*.{ts,tsx}', '!./interfaceLoginName.test.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

describe('介面登入只有一個叫法', () => {
  it('樣式抓得到舊叫法，不誤抓 qBittorrent 的選單路徑（雙向）', () => {
    expect('設定 qBittorrent 的 WebUI 登入').toMatch(OLD_NAME)
    expect('qBittorrent WebUI 的帳號：').toMatch(OLD_NAME)
    expect('Set the qBittorrent WebUI login').toMatch(OLD_NAME)
    expect('qBittorrent WebUI username:').toMatch(OLD_NAME)
    expect('打開它的「選項 → WebUI」，在「驗證」取消勾選').not.toMatch(OLD_NAME)
    expect('open its Options → WebUI and, under Authentication').not.toMatch(OLD_NAME)
    expect('設定 qBittorrent 的介面登入').not.toMatch(OLD_NAME)
    expect('Set the qBittorrent interface login').not.toMatch(OLD_NAME)
  })

  it('web/src 裡搜不到舊叫法', () => {
    const found = Object.entries(SOURCES).flatMap(([path, source]) =>
      source
        .split('\n')
        .map((line, index) => ({ line, index }))
        .filter(({ line }) => OLD_NAME.test(line))
        .map(({ line, index }) => `${path}:${index + 1}: ${line.trim()}`),
    )

    expect(Object.keys(SOURCES).length).toBeGreaterThan(100)
    expect(found).toEqual([])
  })

  describe.each(SUPPORTED_LANGUAGES)('%s', (language) => {
    const { interfaceLogin, qbittorrent } = resources[language].translation
    // 設定頁那一區的標題就是這個詞本身。
    const term = new RegExp(interfaceLogin.settings.title, 'i')

    it('qBittorrent 與 Prowlarr 的登入同一個叫法', () => {
      expect(interfaceLogin.qbittorrent.legend).toMatch(term)
      expect(interfaceLogin.prowlarr.legend).toMatch(term)
      expect(qbittorrent.title.bundled).toMatch(term)
      expect(qbittorrent.cutaway.password).toMatch(term)
      expect(qbittorrent.step.web_ui_password).toMatch(term)
      expect(qbittorrent.setLogin).toMatch(term)
    })
  })
})

import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * 既有服務的接入條件與掛載補法（M4 票 36，審計 §C1、§C2）：容器路徑只能是 `/data`，補法是在原本那一份
 * 多加一條掛載、原本的不動。原本的卡片寫「例如都是 /data」，補法叫人把下載目錄移過去、別分開掛 `/downloads`
 * ——照做的話舊 torrent 找不到檔案。
 */

/** 把 `/data` 說成舉例。 */
const GIVES_EXAMPLE = /例如|e\.g\.|for example|such as/i
/** 叫人搬下載目錄、拿掉原本的掛載。 */
const MOVES_MOUNTS = /移到|不要分開掛|\bmove\b|instead of separate/i
/** 說原本的掛載留著。 */
const KEEPS_MOUNTS = {
  'zh-Hant': /原本的掛載不用動|原本的掛載留著/,
  en: /keep (your|its) existing mounts|existing mounts stay/i,
} as const

describe('三個樣式本身（雙向）', () => {
  it('抓得到原本的寫法', () => {
    expect('把同一個父目錄掛在同一個容器路徑（例如都是 /data）').toMatch(GIVES_EXAMPLE)
    expect('at the same container path (for example /data on both)').toMatch(GIVES_EXAMPLE)
    expect('下載目錄也移到它底下。不要分開掛 /downloads').toMatch(MOVES_MOUNTS)
    expect('and move its download folder under it').toMatch(MOVES_MOUNTS)
    expect('use one /data mount instead of separate /downloads').toMatch(MOVES_MOUNTS)
    expect('多加一條掛載，舊的換掉。').not.toMatch(KEEPS_MOUNTS['zh-Hant'])
    expect('Add one mount and replace the old ones.').not.toMatch(KEEPS_MOUNTS.en)
  })

  it('不誤抓無關的說法', () => {
    expect('它多半沒掛 /data（例如只掛了 /downloads）').not.toMatch(MOVES_MOUNTS)
    expect('remove the container and docker run the new command').not.toMatch(MOVES_MOUNTS)
    expect('容器路徑只能是 /data。原本的掛載留著，多加這一條就好。').not.toMatch(GIVES_EXAMPLE)
    expect('原本的掛載留著：/downloads 繼續做種').toMatch(KEEPS_MOUNTS['zh-Hant'])
    expect('Its existing mounts stay as they are.').toMatch(KEEPS_MOUNTS.en)
    expect('Keep your existing mounts: /tv stays.').toMatch(KEEPS_MOUNTS.en)
  })
})

describe.each(SUPPORTED_LANGUAGES)('既有服務的條件與補法（%s）', (language) => {
  const { choice, routes, jellyfin } = resources[language].translation
  // 頁 3 加不上 Berth 路徑那一句（`AddPathFailures`）與 Route 檢查的補法是同一件事。
  const fixes: [string, string][] = [
    ...Object.entries(routes.fix.existing),
    ['pathFailed', jellyfin.libraries.pathFailed.jellyfin_cannot_see],
  ]

  it('卡片說容器路徑只能是 /data，條件不舉例', () => {
    expect(choice.existing.sameHost).toContain('/data')
    for (const text of [choice.existing.sameHost, choice.existing.library]) {
      expect(text).not.toMatch(GIVES_EXAMPLE)
    }
  })

  it('補法不叫人搬下載目錄、不叫人拿掉原本的掛載', () => {
    for (const [key, text] of fixes) {
      expect(text, key).not.toMatch(MOVES_MOUNTS)
    }
  })

  it('每一個掛載補法都說原本的掛載不用動', () => {
    const keep = KEEPS_MOUNTS[language]
    for (const key of ['qbittorrentMount', 'libraryMount', 'jellyfinMount'] as const) {
      expect(routes.fix.existing[key], key).toMatch(keep)
    }
    expect(jellyfin.libraries.pathFailed.jellyfin_cannot_see).toMatch(keep)
  })
})

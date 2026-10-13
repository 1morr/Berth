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
/**
 * 叫人自己去 Berth 的 `.env` 找值、把 `${DATA_ROOT}` 換掉（審計 P1-6）。片段已經帶著那個值（M4 票 63），
 * 只有 compose 沒傳進來時 `MountFix` 另說一句（`routes.fix.mount.hostUnknown`），補法本身不再說。
 */
const ASKS_FOR_THE_VALUE = /\$\{DATA_ROOT\}/
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
    expect('berth 那一份 .env 的 DATA_ROOT 掛在 /data（${DATA_ROOT} 換成那個值）').toMatch(
      ASKS_FOR_THE_VALUE,
    )
    expect('(replace ${DATA_ROOT} with the value in berth’s .env)').toMatch(ASKS_FOR_THE_VALUE)
  })

  it('不誤抓無關的說法', () => {
    expect('它多半沒掛 /data（例如只掛了 /downloads）').not.toMatch(MOVES_MOUNTS)
    expect('remove the container and docker run the new command').not.toMatch(MOVES_MOUNTS)
    expect('容器路徑只能是 /data。原本的掛載留著，多加這一條就好。').not.toMatch(GIVES_EXAMPLE)
    expect('原本的掛載留著：/downloads 繼續做種').toMatch(KEEPS_MOUNTS['zh-Hant'])
    expect('Its existing mounts stay as they are.').toMatch(KEEPS_MOUNTS.en)
    expect('Keep your existing mounts: /tv stays.').toMatch(KEEPS_MOUNTS.en)
    expect('把 Berth 的 DATA_ROOT 那個資料夾也掛在 /data').not.toMatch(ASKS_FOR_THE_VALUE)
    expect('Berth’s DATA_ROOT folder at {{root}} as well').not.toMatch(ASKS_FOR_THE_VALUE)
  })
})

describe.each(SUPPORTED_LANGUAGES)('既有服務的條件與補法（%s）', (language) => {
  const { choice, routes, jellyfin, connection } = resources[language].translation
  // 頁 3 加不上 Berth 路徑那一句（`AddPathFailures`）、頁 1 與頁 2 看不到 /data 那兩句與 Route 檢查的
  // 補法是同一件事。
  const fixes: [string, string][] = [
    ...Object.entries(routes.fix.existing),
    ['pathFailed', jellyfin.libraries.pathFailed.unseen],
    ['dataUnseen', connection.fix.dataUnseen],
    ['jellyfinDataUnseen', connection.fix.jellyfinDataUnseen],
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
    for (const [key, text] of fixes.slice(-3)) {
      expect(text, key).toMatch(keep)
    }
  })

  it('補法不叫人自己去 .env 找值：片段已經帶著它（M4 票 63）', () => {
    for (const [key, text] of fixes) {
      expect(text, key).not.toMatch(ASKS_FOR_THE_VALUE)
    }
  })
})

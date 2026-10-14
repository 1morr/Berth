import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * M4 票 103：票 68 的 critique 留下的精靈文案（介面登入的叫法在 `interfaceLoginName.test.ts`）。
 *
 * - 頁 1「既有」卡片的字量（會動到什麼、不會動什麼要留著）。
 * - 選了既有之後停掉套件內那一台的 `COMPOSE_PROFILES`：頁 1、2、4 各給一次，改成只在完成頁給（`IdleBundled`），
 *   選的那一頁只指過去。畫面上的那一半在 `SetupPage.consistency.test.tsx`。
 */

/** 頁 1「既有」卡片上的字（`ServiceChoice` 的 Jellyfin 那一張，標題與連結以外的全部）。 */
function jellyfinCard(language: (typeof SUPPORTED_LANGUAGES)[number]): string {
  const { choice } = resources[language].translation
  const lede = choice.existing.lede
    .replace('{{service}}', 'Jellyfin')
    .replace('{{adds}}', choice.existing.adds.jellyfin)
  return [lede, choice.existing.sameHost, choice.existing.floor.jellyfin].join(' ')
}

/**
 * 卡片的字數上限。票 68 時卡片四段（lede、同一台主機的條件、媒體庫那一段、版本下限）zh-Hant 是 563 字、
 * en 是 1420 字，critique 說太多；媒體庫那一段併進 `adds` 之後，上限約是那時的三分之二。
 */
const CARD_BUDGET = { 'zh-Hant': 370, en: 950 } as const

/** 卡片要說的事：會動到什麼、什麼時候動，以及不動什麼。 */
const CARD_FACTS = {
  'zh-Hant': {
    apiKey: /API key「Berth」/,
    path: /頁 3[^。]*路徑/,
    keepsPaths: /原本的路徑不動/,
    keepsSettings: /不改你原本的設定/,
    newLibraryOnlyIfTicked: /勾了才新建/,
    newLibraryVisibleToAll: /所有使用者都看得到/,
    refreshesOneLibrary: /只請它刷新那個媒體庫/,
    startupWizard: /初始精靈/,
    wholeServerScan: /整台/,
    sameHost: /同一台主機/,
    dataOnly: /只能是 \/data/,
    hardLinks: /硬鏈接/,
  },
  en: {
    apiKey: /API key named Berth/,
    path: /path[^.]*page 3/,
    keepsPaths: /existing paths stay/,
    keepsSettings: /leaves your settings alone/,
    newLibraryOnlyIfTicked: /creates a library only if you tick/,
    newLibraryVisibleToAll: /every user sees it/,
    refreshesOneLibrary: /refresh just that library/,
    startupWizard: /startup wizard/,
    wholeServerScan: /whole server/,
    sameHost: /same host/,
    dataOnly: /only \/data/,
    hardLinks: /hard links/,
  },
} as const

describe.each(SUPPORTED_LANGUAGES)('頁 1「既有」卡片（%s）', (language) => {
  const text = jellyfinCard(language)

  it('在字數上限之內；多一段就超過（雙向）', () => {
    expect(text.length).toBeLessThanOrEqual(CARD_BUDGET[language])
    expect(`${text} ${text.slice(0, text.length / 2)}`.length).toBeGreaterThan(
      CARD_BUDGET[language],
    )
  })

  it.each(Object.entries(CARD_FACTS[language]))('說得出：%s', (_, fact) => {
    expect(text).toMatch(fact)
  })

  it.each(Object.entries(CARD_FACTS[language]))('只說一次：%s', (_, fact) => {
    expect(saysOnce(text, fact)).toBe(true)
  })
})

/** 那一件事只在一句裡說：拿掉說它的那一句之後就說不出。 */
function saysOnce(text: string, fact: RegExp): boolean {
  const sentence = text.split(/(?<=[。；.;])\s*/).find((each) => fact.test(each))
  return sentence !== undefined && !fact.test(text.replace(sentence, ''))
}

describe('saysOnce（雙向）', () => {
  it('說了兩次、沒說都不算', () => {
    expect(saysOnce('只在頁 1 建 API key。頁 3 再建一次 API key。', /API key/)).toBe(false)
    expect(saysOnce('只在頁 3 加路徑。', /API key/)).toBe(false)
    expect(saysOnce('Creates an API key. Then another API key.', /API key/)).toBe(false)
  })

  it('換標點、換斷句照樣算一次', () => {
    expect(saysOnce('只在頁 1 建 API key；頁 3 加路徑。', /API key/)).toBe(true)
    expect(saysOnce('只在頁 1 建 API key，頁 3 加路徑', /API key/)).toBe(true)
    expect(saysOnce('Creates an API key; adds a path on page 3.', /API key/)).toBe(true)
  })
})

/** 說出 `.env` 怎麼改、給停掉的指令。 */
const GIVES_COMMANDS = /COMPOSE_PROFILES|docker compose/

describe.each(SUPPORTED_LANGUAGES)('選了既有那一頁只指向完成頁（%s）', (language) => {
  const { choice, complete } = resources[language].translation

  it('不給 COMPOSE_PROFILES 與停掉的指令，完成頁照給（雙向）', () => {
    expect(choice.existing.idle).not.toMatch(GIVES_COMMANDS)
    expect(complete.idle.body).toMatch(GIVES_COMMANDS)
  })

  it('說得出去哪一段找', () => {
    expect(choice.existing.idle).toContain('{{section}}')
  })
})

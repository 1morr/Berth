import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

/**
 * 審計「文件與實作不符」表上前面的票沒涵蓋的幾句（M4 票 53）：
 *
 * - 既有 Jellyfin 卡片只說頁 3 加路徑，沒說頁 1 會在它上面建 API key「Berth」。
 * - 頁 4 還沒選時的 lede 說你自己的 Prowlarr「用你已經有的站」，卡片與選了之後的 lede 都說也能加站（M4 票 20）；
 *   選了之後的 lede 與回頭看的說明又說「按一次加進去」，實際是測過、勾選、確認才加（卡片說「勾起來的站」）。
 * - 套件內 qBittorrent 不收 Berth 時叫人重啟、說預置腳本會補上白名單；預置腳本只補設定檔裡**沒有**的鍵
 *   （`deploy/preseed/qbittorrent/10-berth.sh`），在 WebUI 關掉白名單之後重啟補不回來（票 53 實跑）。
 */

/** 卡片說了 API key「Berth」。 */
const NAMES_THE_KEY = /API key\s*[「“"]?Berth|key (named|called) Berth/i
/** 說你自己的那一台也能加站。 */
const EXISTING_ADDS_SITES = /也(可以|能)加|can also add|may also add/i
/** 說按一次就加進去（既有那一台是勾選之後才加）。 */
const ONE_PRESS = /按一次加|in one press/i
/** 說重啟會把白名單補回來。 */
const RESTART_RESTORES =
  /重啟[^。；]{0,15}(補上|補回來)|restart[^.]{0,40}\b(adds|restores|brings back|puts back)\b/i
/**
 * qBittorrent WebUI 那一格的標籤（brief §20.7，5.0 的 webui_zh_TW.ts 與 preferences.html）。逐字比對是刻意的：
 * 使用者要在 WebUI 上找到同一串字，換個說法就找不到。
 */
const ALLOWLIST_OPTION = {
  'zh-Hant': '讓已在白名單中的 IP 子網路略過驗證',
  en: 'Bypass authentication for clients in whitelisted IP subnets',
} as const

describe('四個樣式本身（雙向）', () => {
  it('抓得到原本的寫法', () => {
    expect('重啟它讓預置腳本補上白名單，再重新測試：').toMatch(RESTART_RESTORES)
    expect('Restart it so the preseed script adds the allowlist, then test again:').toMatch(
      RESTART_RESTORES,
    )
    expect('只在頁 3 你按下時替媒體庫多加一條 Berth 寫入用的路徑').not.toMatch(NAMES_THE_KEY)
    expect('only adds one path for Berth to write to on a library').not.toMatch(NAMES_THE_KEY)
    expect('你自己的那一台貼 API key，用你已經有的站。').not.toMatch(EXISTING_ADDS_SITES)
    expect('Berth uses the indexers you already have.').not.toMatch(EXISTING_ADDS_SITES)
  })

  it('換個說法照樣抓得到', () => {
    expect('也可以測試推薦的公開站、按一次加進去').toMatch(ONE_PRESS)
    expect('test the recommended public sites and add them in one press').toMatch(ONE_PRESS)
    expect('也可以測試推薦的公開站、勾選通過的加進去').not.toMatch(ONE_PRESS)
    expect('按一次，Berth 測試推薦的站').not.toMatch(ONE_PRESS)
    expect('重啟它，預置腳本會補上白名單。').toMatch(RESTART_RESTORES)
    expect('Restart it and the preseed script restores the allowlist.').toMatch(RESTART_RESTORES)
    expect('頁 1 建一把名為 Berth 的 API key').not.toMatch(NAMES_THE_KEY)
  })

  it('不誤抓無關的說法', () => {
    expect('預置腳本只補設定檔裡沒有的鍵，重啟不會蓋掉你改過的。').not.toMatch(RESTART_RESTORES)
    expect('Restarting it does not undo what you changed.').not.toMatch(RESTART_RESTORES)
    expect('頁 1 在它上面建一把 API key「Berth」').toMatch(NAMES_THE_KEY)
    expect('頁 1 在它上面建 API key "Berth"').toMatch(NAMES_THE_KEY)
    expect('creates an API key named Berth on it').toMatch(NAMES_THE_KEY)
    expect('creates a key called Berth').toMatch(NAMES_THE_KEY)
    expect('用它已經有的站，也可以加推薦的公開站').toMatch(EXISTING_ADDS_SITES)
    expect('用它已經有的站，也能加公開站').toMatch(EXISTING_ADDS_SITES)
    expect('and you can also add recommended public sites').toMatch(EXISTING_ADDS_SITES)
    expect('重啟補不回來：預置腳本不蓋掉你改過的。').not.toMatch(RESTART_RESTORES)
    expect('A restart will not bring it back.').not.toMatch(RESTART_RESTORES)
  })
})

describe.each(SUPPORTED_LANGUAGES)('文件與實作不符的幾句（%s）', (language) => {
  const { choice, connection, indexer, setup } = resources[language].translation

  it('既有 Jellyfin 卡片說頁 1 會建 API key「Berth」', () => {
    expect(choice.existing.adds.jellyfin).toMatch(NAMES_THE_KEY)
  })

  it('頁 4 還沒選時就說你自己的 Prowlarr 也能加站', () => {
    expect(indexer.lede.choose).toMatch(EXISTING_ADDS_SITES)
  })

  it('既有 Prowlarr 的加站不說成按一次', () => {
    expect(indexer.lede.existing).not.toMatch(ONE_PRESS)
    expect(setup.revisit.indexer.existing.can).not.toMatch(ONE_PRESS)
  })

  it('白名單的補法說 WebUI 那一格，不說重啟會補回來', () => {
    expect(connection.fix.whitelist).not.toMatch(RESTART_RESTORES)
    expect(connection.fix.whitelist).toContain(ALLOWLIST_OPTION[language])
  })
})

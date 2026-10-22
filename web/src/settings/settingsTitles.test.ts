import { describe, expect, it } from 'vitest'

import { BERTHS } from '../components/berths'
import { resources, SUPPORTED_LANGUAGES } from '../i18n/resources'

/**
 * 設定頁的標題說出它分頁上的名字（M4 票 132）：英文的分頁是泊位名「Library paths」，那一頁的 h1 與精靈頁 3
 * 卻寫「Routes」，各處「Settings → Library paths」的指路句找得到分頁、點進去標題對不上。
 * 中文本來就兩邊都是「媒體庫路徑」。
 */

/**
 * 泊位分頁 → 那一頁的標題 key（Route 頁不走 `SettingsFrame`，另加精靈頁 3 的標題：它也是這一格）。
 * 「通知」不是泊位，英文分頁 `Notifications` 與標題 `Notification settings` 是同一個詞的兩種文法，不列。
 */
const TITLES: Record<string, readonly string[]> = {
  'board.jellyfin': ['settings.jellyfinPage.title'],
  'board.qbittorrent': ['settings.qbittorrentPage.title'],
  'board.library': ['routeSettings.title', 'routes.title'],
  'board.indexers': ['settings.indexerPage.title'],
  'board.tmdb': ['settings.tmdbPage.title'],
}

function lookup(table: unknown, key: string): string {
  const value = key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], table)
  if (typeof value !== 'string') throw new Error(`${key} 不是字串`)
  return value
}

/** 標題說得出分頁名：大小寫不計（`Jellyfin settings` 對 `Jellyfin`）。 */
function namesTab(title: string, tab: string): boolean {
  return title.toLowerCase().includes(tab.toLowerCase())
}

describe('設定頁標題對得上分頁名', () => {
  it('判準抓得到分頁與標題各叫各的，不誤抓大小寫與後綴（雙向）', () => {
    expect(namesTab('Routes', 'Library paths')).toBe(false)
    expect(namesTab('通知', '媒體庫路徑')).toBe(false)
    expect(namesTab('Library paths', 'Library paths')).toBe(true)
    expect(namesTab('Prowlarr 設定', 'Prowlarr')).toBe(true)
    expect(namesTab('qBittorrent settings', 'QBittorrent')).toBe(true)
  })

  it('每一格泊位都有標題對照，沒有漏掉的分頁', () => {
    expect(Object.keys(TITLES).sort()).toEqual(BERTHS.map((berth) => berth.nameKey).sort())
  })

  it.each(SUPPORTED_LANGUAGES)('%s：每一頁的標題含它分頁的名字', (language) => {
    const table = resources[language].translation
    const mismatched = Object.entries(TITLES).flatMap(([tabKey, titleKeys]) => {
      const tab = lookup(table, tabKey)
      return titleKeys
        .map((titleKey) => lookup(table, titleKey))
        .filter((title) => !namesTab(title, tab))
        .map((title) => `${tab} ≠ ${title}`)
    })
    expect(mismatched).toEqual([])
  })
})

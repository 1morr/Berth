import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from './resources'

type Tree = { readonly [key: string]: string | Tree }

/**
 * 值裡帶 `{{count}}`、卻不是 `_one` / `_other` 一對的鍵。
 *
 * i18next 收到 `count` 時查的是 `key_one` / `key_other`，兩個都沒有就退回原鍵——於是英文在只有一筆時
 * 說「1 routes」，而且沒有任何東西會紅（CHANGELOG 記過探索頁的那一個，票 15 收掉其餘的）。
 * 中文的兩個值通常一樣，照樣要成對：規則對兩個語言是同一條，鍵樹才對得起來。
 */
function pluralGaps(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value !== 'string') return pluralGaps(value, path)
    if (!value.includes('{{count}}')) return []
    const base = key.replace(/_(one|other)$/, '')
    const paired = base !== key && `${base}_one` in tree && `${base}_other` in tree
    return paired ? [] : [path]
  })
}

describe('plural keys', () => {
  it.each(SUPPORTED_LANGUAGES)('every count in %s has a _one and an _other', (language) => {
    expect(pluralGaps(resources[language].translation)).toEqual([])
  })

  it('catches a count that has no plural pair', () => {
    expect(pluralGaps({ health: { routes: { count: '{{count}} routes' } } })).toEqual([
      'health.routes.count',
    ])
  })

  it('catches half a pair', () => {
    expect(pluralGaps({ drift: { changed_one: '{{count}} key differs' } })).toEqual([
      'drift.changed_one',
    ])
  })

  it('leaves pairs, other placeholders and plain strings alone wherever they sit', () => {
    expect(
      pluralGaps({
        files_one: '{{count}} file',
        files_other: '{{count}} files',
        deep: {
          nested: {
            idle_one: '{{count}} minute quiet',
            idle_other: '{{count}} minutes quiet',
          },
        },
        done: 'Deleted “{{name}}”.',
        title: 'Library routes',
      }),
    ).toEqual([])
  })
})

/**
 * 寫死檢查條數的文案（M4 票 31）。
 *
 * Route 的檢查從五條長成六條（M4 票 19 加了 `download_visible`），七個鍵還寫著「五條纜繩」——條數住在
 * `CHECK_LABEL`，文案不跟著它改。所以文案不寫條數；要數字就用 `{{count}}` 從程式帶進來。
 * 「一條」不算：「每一條」「哪一條纜繩」說的是其中一條，不是總數。
 */
const COUNTED_CHECKS =
  /[二兩三四五六七八九十\d]+\s*條(纜繩|檢查)|\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(checks|cables)\b/i

function countedChecks(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value !== 'string') return countedChecks(value, path)
    return COUNTED_CHECKS.test(value) ? [path] : []
  })
}

describe('route check counts', () => {
  it.each(SUPPORTED_LANGUAGES)('no %s copy writes down how many checks a route has', (language) => {
    expect(countedChecks(resources[language].translation)).toEqual([])
  })

  it('catches a fixed count in either language', () => {
    expect(
      countedChecks({
        zh: { rerun: '啟用時會先把五條纜繩重跑一次。', six: '六條檢查都要綠燈' },
        en: { rerun: 'Enabling it runs the five checks again.', digits: 'all 6 checks passed' },
      }),
    ).toEqual(['zh.rerun', 'zh.six', 'en.rerun', 'en.digits'])
  })

  it('leaves counted placeholders, berths and other counts alone', () => {
    expect(
      countedChecks({
        passed: '{{passed}} / {{total}} 通過',
        berths: '五個泊位都走過了。',
        enBerths: 'All five berths have been visited.',
        every: '每一條 Route 的每一條纜繩都要綠燈。',
        which: '到健康頁看是哪一條纜繩斷了。',
        counted: '{{count}} checks failed',
        sites: 'Prowlarr already has 5 sites.',
      }),
    ).toEqual([])
  })
})

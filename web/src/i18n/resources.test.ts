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

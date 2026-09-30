import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from '../i18n/resources'
import { FAILURE_TEXT } from './failures'

type Tree = { readonly [key: string]: string | Tree }

/** `keys` 裡在這一棵鍵樹上不是一句字串的那幾個（沒有、或是一整個分支）。 */
function untranslated(keys: readonly string[], tree: Tree): string[] {
  return keys.filter((key) => {
    const value = key
      .split('.')
      .reduce<string | Tree | undefined>(
        (node, part) => (typeof node === 'object' ? node[part] : undefined),
        tree,
      )
    return typeof value !== 'string' || value.trim() === ''
  })
}

/**
 * 每個錯誤代碼兩個語言都有一句人話（M4 票 21）。`FAILURE_TEXT` 的 `satisfies` 讓後端多一個代碼時 tsc 就紅；
 * 這裡守的是另一半：對照表指到的 key 在兩棵鍵樹裡真的有字——缺了的話畫面印出 key 本身。
 */
describe('failure codes', () => {
  const keys = Object.values(FAILURE_TEXT)

  it.each(SUPPORTED_LANGUAGES)('every code has a sentence in %s', (language) => {
    expect(keys.length).toBeGreaterThan(20)
    expect(untranslated(keys, resources[language].translation)).toEqual([])
  })

  it('catches a code whose sentence is missing, empty or a branch', () => {
    const tree = {
      failure: { unreachable: 'Cannot reach {{service}}.', starting: '', library_gone: { x: 'y' } },
    }
    expect(
      untranslated(
        ['failure.unreachable', 'failure.starting', 'failure.library_gone', 'failure.not_found'],
        tree,
      ),
    ).toEqual(['failure.starting', 'failure.library_gone', 'failure.not_found'])
  })
})

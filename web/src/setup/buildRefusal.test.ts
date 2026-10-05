import { describe, expect, it } from 'vitest'

import { resources, SUPPORTED_LANGUAGES } from '../i18n/resources'
import { BUILD_REFUSAL } from './buildRefusal'

type Tree = { readonly [key: string]: string | Tree }

/** `keys` 裡在這一棵鍵樹上不是一句字串的那幾個（與 `failures.test.ts` 同一個做法）。 */
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
 * 頁 3 建 Route 被拒的每一種理由兩個語言都有一句（M4 票 31）。`BUILD_REFUSAL` 指到的 key 缺了的話，
 * 畫面印出 key 本身——`strictKeyChecks` 看不到查表之後的字串。
 */
describe('route build refusals', () => {
  it.each(SUPPORTED_LANGUAGES)('every reason has a sentence in %s', (language) => {
    expect(untranslated(Object.values(BUILD_REFUSAL), resources[language].translation)).toEqual([])
  })

  it('catches a missing or empty sentence', () => {
    const tree = { routes: { refused: { library_missing: 'Gone.', library_unsupported: '' } } }
    expect(
      untranslated(
        [
          'routes.refused.library_missing',
          'routes.refused.library_unsupported',
          'routes.refused.library_without_path',
        ],
        tree,
      ),
    ).toEqual(['routes.refused.library_unsupported', 'routes.refused.library_without_path'])
  })
})

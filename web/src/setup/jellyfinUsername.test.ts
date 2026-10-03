import { describe, expect, it } from 'vitest'

import { trimUsername, usernameProblem } from './jellyfinUsername'

describe('trimUsername（M4 票 29：頁 1 與登入頁同一條修剪規則）', () => {
  it('去掉前後空白，中間的不動', () => {
    expect(trimUsername('  skipper  ')).toBe('skipper')
    expect(trimUsername('\tfirst mate\n')).toBe('first mate')
  })
})

/** Jellyfin 12.1 `UserManager.ValidUsernameRegex` 與 `ThrowIfInvalidUsername`（brief §20.7）。 */
describe('usernameProblem', () => {
  it.each(['skipper', '船長', 'first mate', "o'brien", 'a.b@c+d-e_f', 'José', 'ナミ', '..x'])(
    'Jellyfin 收 %j',
    (name) => {
      expect(usernameProblem(name)).toBeNull()
    },
  )

  // 實測 B2-05～07 被 400 的六個字元，加上規則外的其他符號與空白以外的空白字元。
  it.each(['a<b', 'a>b', 'a&b', 'a"b', 'a/b', 'a\b', 'a:b', 'a#b', 'a!b', 'tab\tin', 'é😀'])(
    'Jellyfin 不收 %j',
    (name) => {
      expect(usernameProblem(name)).toBe('characters')
    },
  )

  it('只是一個或兩個點也不收', () => {
    expect(usernameProblem('.')).toBe('characters')
    expect(usernameProblem('..')).toBe('characters')
  })

  it('空的與只有空白的是「要填」，不是字元不對', () => {
    expect(usernameProblem('')).toBe('blank')
    expect(usernameProblem('   ')).toBe('blank')
  })

  it('看的是修剪之後的帳號：前後空白不算違規', () => {
    expect(usernameProblem('  skipper ')).toBeNull()
  })
})

import { describe, expect, it } from 'vitest'

import { LOGIN_RULES, loginProblems, takenLogin } from './interfaceLogin'

describe('loginProblems（M4 票 07：兩格都必填、密碼打兩次）', () => {
  it('帳號、密碼、再一次都對得上就沒有問題', () => {
    expect(loginProblems({ username: 'skipper', password: 'harbour', confirm: 'harbour' })).toEqual(
      {},
    )
  })

  it('空的帳號與密碼各自說要填；只有空白的帳號也算空', () => {
    expect(loginProblems({ username: '  ', password: '', confirm: '' })).toEqual({
      username: 'blank',
      password: 'blank',
    })
  })

  it('兩次密碼不同才說不一樣；密碼還是空的時候只說要填', () => {
    expect(loginProblems({ username: 'skipper', password: 'harbour', confirm: 'harbor' })).toEqual({
      confirm: 'mismatch',
    })
    expect(loginProblems({ username: 'skipper', password: '', confirm: 'harbour' })).toEqual({
      password: 'blank',
    })
  })
})

describe('沿用 Jellyfin 帳密（M4 票 15）', () => {
  /** 帳號是擁有者、密碼打一次：Jellyfin 會驗它，打錯了有人會說（票 06「兩次只在建立時」的反面）。 */
  it('只要密碼那一格：帳號與再一次都不看', () => {
    expect(
      loginProblems({ username: '', password: 'harbour', confirm: '' }, { reuse: true }),
    ).toEqual({})
    expect(loginProblems({ username: '', password: '', confirm: '' }, { reuse: true })).toEqual({
      password: 'blank',
    })
  })

  it('送出去的是「沿用」，帳號留給後端填', () => {
    expect(takenLogin({ username: 'typed', password: 'harbour', confirm: '' }, true)).toEqual({
      username: '',
      password: 'harbour',
      reuse_owner: true,
    })
  })

  it('取消勾選就是自設的那一組，帳號去空白', () => {
    expect(takenLogin({ username: ' deck ', password: 'rope', confirm: 'rope' }, false)).toEqual({
      username: 'deck',
      password: 'rope',
      reuse_owner: false,
    })
  })
})

describe('qBittorrent 的帳密規則（M4 票 26，brief §20.2）', () => {
  const rules = LOGIN_RULES.qbittorrent
  const own = (username: string, password: string) =>
    loginProblems({ username, password, confirm: password }, { rules })
  const reused = (owner: string, password: string) =>
    loginProblems({ username: '', password, confirm: '' }, { reuse: true, rules, owner })

  it('密碼短於 6 字元擋下，剛好 6 字元通過；字數照 String.length（六個中文字也是 6）', () => {
    expect(own('skipper', 'abcde')).toEqual({ password: 'short' })
    expect(own('skipper', 'abcdef')).toEqual({})
    expect(own('skipper', '密碼密碼密碼')).toEqual({})
  })

  it('帳號短於 3 字元或有冒號擋下；去掉前後空白再數', () => {
    expect(own('ab', 'abcdef')).toEqual({ username: 'short' })
    expect(own(' ab ', 'abcdef')).toEqual({ username: 'short' })
    expect(own('ab:c', 'abcdef')).toEqual({ username: 'colon' })
    expect(own('abc', 'abcdef')).toEqual({})
  })

  it('沿用時照樣檢查：Jellyfin 密碼太短、擁有者的名字不合規則都不能沿用', () => {
    expect(reused('skipper', 'abcd')).toEqual({ password: 'short' })
    expect(reused('jo', 'Harbour-1')).toEqual({ username: 'short' })
    expect(reused('j:o', 'Harbour-1')).toEqual({ username: 'colon' })
    expect(reused('skipper', 'Harbour-1')).toEqual({})
  })

  it('沒有規則的服務（Prowlarr）只要填了就好', () => {
    expect(
      loginProblems(
        { username: 'jo', password: 'abc', confirm: 'abc' },
        { rules: LOGIN_RULES.prowlarr },
      ),
    ).toEqual({})
  })
})

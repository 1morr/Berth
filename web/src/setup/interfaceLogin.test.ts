import { describe, expect, it } from 'vitest'

import { loginProblems, takenLogin } from './interfaceLogin'

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
    expect(loginProblems({ username: '', password: 'harbour', confirm: '' }, true)).toEqual({})
    expect(loginProblems({ username: '', password: '', confirm: '' }, true)).toEqual({
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
    expect(
      takenLogin({ username: ' deck ', password: 'rope', confirm: 'rope' }, false),
    ).toEqual({ username: 'deck', password: 'rope', reuse_owner: false })
  })
})

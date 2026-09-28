import { describe, expect, it } from 'vitest'

import { loginProblems } from './interfaceLogin'

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

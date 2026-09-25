import { describe, expect, it } from 'vitest'

import { maskToken } from './maskToken'

describe('maskToken', () => {
  it('聚合 feed 的 token 只留前四碼', () => {
    expect(maskToken('https://mikanani.me/RSS/MyBangumi?token=abcdef123456%3d%3d')).toBe(
      'https://mikanani.me/RSS/MyBangumi?token=abcd…',
    )
  })

  it('其他參數與沒有 token 的網址不動', () => {
    expect(maskToken('https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370')).toBe(
      'https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370',
    )
    expect(maskToken('https://mikanani.me/RSS/MyBangumi?x=1&token=abcdefgh&y=2')).toBe(
      'https://mikanani.me/RSS/MyBangumi?x=1&token=abcd…&y=2',
    )
  })
})

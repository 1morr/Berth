import { describe, expect, it } from 'vitest'

import type { TFunction } from 'i18next'

import { addressError, lacksScheme } from './address'

describe('lacksScheme（M4 票 25：位址要寫明 http:// 或 https://）', () => {
  it.each(['192.168.1.5:8080', 'nas:8080', 'localhost:8096', 'qbittorrent', 'ftp://nas:21'])(
    '%s 沒有 http(s) 協定',
    (address) => {
      expect(lacksScheme(address)).toBe(true)
    },
  )

  it.each(['http://nas:8080', 'https://jellyfin.example.com', '  HTTP://NAS:8080  '])(
    '%s 有',
    (address) => {
      expect(lacksScheme(address)).toBe(false)
    },
  )

  it('空的不算：那是「必填」那一句的事', () => {
    expect(lacksScheme('   ')).toBe(false)
  })
})

describe('addressError：送出前欄位下的那一句，有它就不送', () => {
  const t = ((key: string) => key) as unknown as TFunction

  it.each([
    ['', 'connect.error.blank'],
    ['nas:8080', 'connect.error.scheme'],
    ['http://nas:8080', undefined],
  ])('%j → %s', (address, error) => {
    expect(addressError(t, address)).toBe(error)
  })
})

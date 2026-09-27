import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { destination, home, internalRedirect } from './destination'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('登入後要去哪裡', () => {
  it('Berth 入庫過東西的人落在媒體庫：接著看的兩列在那裡', () => {
    expect(home(true)).toBe('/library')
  })

  // 精靈剛跑完的那一次登入也是這一條：那時 Berth 還一筆都沒入庫過（brief §19 2026-09-26）。
  it('媒體庫裡還沒有 Berth 入庫的東西時落在探索：第一件事是找片', () => {
    expect(home(false)).toBe('/')
  })

  it('站內的 `?redirect=` 照收', () => {
    expect(internalRedirect('/settings/tmdb')).toBe('/settings/tmdb')
    expect(internalRedirect(undefined)).toBeUndefined()
  })

  it.each(['https://evil.example', '//evil.example', '/\\evil.example', 'settings'])(
    '站外或不是路徑的 `%s` 不算',
    (redirect) => {
      expect(internalRedirect(redirect)).toBeUndefined()
    },
  )
})

describe('問媒體庫', () => {
  // 問不到時落在媒體庫，由它說 Jellyfin 為什麼答不了。不重試：登入按鈕在那幾秒一直停在「登入中」，
  // 而媒體庫頁自己還會再問一次。
  it('沒有理由的 5xx 只問一次就落到媒體庫', async () => {
    const api = stubApi({ 'GET /api/inventory': { status: 502, body: { detail: 'Bad Gateway' } } })

    expect(await destination(new QueryClient(), undefined)).toBe('/library')
    expect(api).toHaveBeenCalledTimes(1)
  })

  it('有去處就不問', async () => {
    const api = stubApi({})

    expect(await destination(new QueryClient(), '/jobs')).toBe('/jobs')
    expect(api).not.toHaveBeenCalled()
  })
})

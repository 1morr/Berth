import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { retryUnlessRefused } from './jellyfin'

describe('媒體庫查詢的重試', () => {
  it('說得出理由的拒絕不重試：那是答案，不是故障', () => {
    const refused = new ApiError(404, 'GET /inventory/anime failed with 404', {
      reason: 'library_not_visible',
      detail: 'no such library, or not yours to see',
    })

    expect(retryUnlessRefused(0, refused)).toBe(false)
  })

  it('沒有理由的錯誤照預設重試三次', () => {
    const offline = new ApiError(502, 'GET /inventory failed with 502')

    expect(retryUnlessRefused(0, offline)).toBe(true)
    expect(retryUnlessRefused(2, offline)).toBe(true)
    expect(retryUnlessRefused(3, offline)).toBe(false)
    expect(retryUnlessRefused(0, new TypeError('Failed to fetch'))).toBe(true)
  })
})

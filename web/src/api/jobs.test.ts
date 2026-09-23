import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { jobQueryOptions } from './jobs'

/**
 * 詳情頁的那一支查詢不重試後端的回答（M2 票 12 實跑抓到）：TanStack Query 預設重試三次、間隔加倍，
 * 不存在的 hash 要等七秒才畫得出「找不到這筆下載」。測試的 QueryClient 關掉了重試，所以這一條
 * 只能在查詢自己的選項上釘住。
 */
describe('jobQueryOptions 的重試', () => {
  const retry = jobQueryOptions('a'.repeat(40)).retry

  function retries(failures: number, error: Error): boolean {
    if (typeof retry !== 'function') throw new Error('retry must be a function')
    return retry(failures, error)
  }

  it('404 是答案：那一筆不存在，不重試', () => {
    expect(retries(0, new ApiError(404, 'no such job'))).toBe(false)
  })

  it('後端回了任何狀態碼都不重試：同源的 Berth 回 5xx 是它自己的錯，重試只是晚七秒說', () => {
    expect(retries(0, new ApiError(500, 'boom'))).toBe(false)
  })

  it('網路層失敗照預設重試三次', () => {
    expect(retries(0, new TypeError('Failed to fetch'))).toBe(true)
    expect(retries(2, new TypeError('Failed to fetch'))).toBe(true)
    expect(retries(3, new TypeError('Failed to fetch'))).toBe(false)
  })
})

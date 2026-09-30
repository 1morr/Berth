import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { requestProblem } from './requestProblem'

/**
 * 對 Berth 自己的請求為什麼沒成（M4 票 21）。原本一律說「Berth 後端可能沒在跑」——選擇無效的 422
 * 也是，於是使用者去查一個活得好好的容器。
 */
describe('requestProblem', () => {
  it('送不到（沒有 HTTP 回應）才是沒在跑或斷線', () => {
    expect(requestProblem(new TypeError('Failed to fetch'))).toBe('offline')
  })

  it('422 是這一次送的東西它不收，409 是與現狀衝突，其餘是它自己出錯', () => {
    expect(requestProblem(new ApiError(422, 'POST /setup/routes failed with 422'))).toBe('invalid')
    expect(requestProblem(new ApiError(409, 'POST /setup/routes failed with 409'))).toBe('conflict')
    expect(requestProblem(new ApiError(500, 'POST /setup/routes failed with 500'))).toBe('server')
    expect(requestProblem(new ApiError(502, 'POST /setup/owner failed with 502'))).toBe('server')
  })
})

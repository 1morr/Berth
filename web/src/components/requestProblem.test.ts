import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { ApiError } from '../api/client'
import { problemText, requestProblem } from './requestProblem'

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

  // M4 票 25（實測 E10-05、E12-11）：門禁的 401 / 403 原本落到「後端出錯了」或「後端可能沒在跑」。
  it('403：擁有者成立之後是不是管理員；之前是門禁說「先做完頁 1」，畫面走在後端前面', () => {
    const refused = new ApiError(403, 'GET /setup/routes failed with 403')

    expect(requestProblem(refused)).toBe('notAdministrator')
    expect(requestProblem(refused, { ownerPending: true })).toBe('conflict')
  })

  it('401：這一頁讀到的精靈還沒有擁有者，就是擁有者在別處成立了；否則是登入失效', () => {
    const refused = new ApiError(401, 'POST /setup/owner failed with 401')

    expect(requestProblem(refused, { ownerPending: true })).toBe('ownerElsewhere')
    expect(requestProblem(refused)).toBe('signedOut')
    expect(requestProblem(refused, { ownerPending: false })).toBe('signedOut')
  })
})

/** 只收字串的那幾格（M4 票 89）：前半句是呼叫端的，後半句照請求為什麼沒成。 */
describe('problemText', () => {
  const t = i18next.getFixedT('zh-Hant')

  it('前半句接在前面，中間一個空白', () => {
    expect(problemText(t, new ApiError(500, 'x'), '沒有成功。')).toBe(
      '沒有成功。 Berth 的後端出錯了。再試一次；還是不行的話看 berth 容器的 log。',
    )
  })

  it('500、401、送不到各說各的原因', () => {
    const texts = [
      new ApiError(500, 'x'),
      new ApiError(401, 'x'),
      new TypeError('Failed to fetch'),
    ].map((error) => problemText(t, error))
    expect(texts).toEqual([t('request.server'), t('request.signedOut'), t('request.offline')])
  })

  it('沒有前半句時只剩原因', () => {
    expect(problemText(t, new TypeError('Failed to fetch'))).toBe(t('request.offline'))
  })
})

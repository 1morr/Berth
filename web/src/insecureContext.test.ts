import { describe, expect, it } from 'vitest'

/**
 * 單元測試跑在「區網 IP 走 HTTP」的瀏覽器裡（`setupTests.ts`）：使用者多半這樣開 Berth，而 jsdom 預設
 * 什麼都給，0.4.0 的 `crypto.randomUUID` crash 因此在每一層測試都綠著出貨。
 */
describe('測試環境像 HTTP 下的瀏覽器', () => {
  it('沒有只在 secure context 才有的 API', () => {
    expect(window.isSecureContext).toBe(false)
    expect(crypto.randomUUID).toBeUndefined()
    expect(crypto.subtle).toBeUndefined()
    expect(navigator.clipboard).toBeUndefined()
  })

  it('其他照常：產生隨機數不受影響', () => {
    expect(crypto.getRandomValues(new Uint8Array(4))).toHaveLength(4)
  })
})

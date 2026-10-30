import { afterEach, describe, expect, it } from 'vitest'

import { rememberNewConversation } from './panelState'

describe('新對話的 id', () => {
  afterEach(() => {
    localStorage.clear()
  })

  // 用區網 IP 走 HTTP 開 Berth 時不是 secure context，瀏覽器不給 `crypto.randomUUID`（測試環境也不給，
  // `setupTests.ts`）；0.4.0 在這種情況下整頁 crash（「crypto.randomUUID is not a function」）。
  it('不是 secure context（沒有 randomUUID）也開得出一段新對話', () => {
    const id = rememberNewConversation()

    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(localStorage.getItem('berth.agent.conversation')).toBe(id)
  })

  it('每次都不一樣', () => {
    expect(rememberNewConversation()).not.toBe(rememberNewConversation())
  })
})

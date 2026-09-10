import { renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useJobStream } from './events'

/**
 * SSE 訂閱（`.scratch/m1/live-jobs-shape.md` §6、票 10）。
 *
 * jsdom 沒有 `EventSource`，所以這裡自己擺一個——順便讓「沒有 EventSource 的環境不該爆掉」
 * 這件事在其他測試裡自然成立（那些測試沒有這個替身，而下載列表照樣畫得出來）。
 */

class FakeEventSource {
  static opened: FakeEventSource[] = []

  readonly listeners = new Map<string, EventListener>()
  readonly url: string
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.opened.push(this)
  }

  addEventListener(type: string, listener: EventListener): void {
    this.listeners.set(type, listener)
  }

  removeEventListener(type: string): void {
    this.listeners.delete(type)
  }

  close(): void {
    this.closed = true
  }

  emit(type: string, data: string): void {
    this.listeners.get(type)?.(new MessageEvent(type, { data }))
  }
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidate = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
  const view = renderHook(() => useJobStream(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })
  return { view, invalidate, source: FakeEventSource.opened.at(-1) as FakeEventSource }
}

afterEach(() => {
  FakeEventSource.opened = []
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('job 推播', () => {
  it('連上的那一刻先重問一次——訂閱之前推出去的那幾筆誰都收不到', () => {
    // 實跑當場踩到的：送單後那一筆在頁面還在連線時就完成了，於是畫面停在
    // 「已取得檔案清單」再也不動。同一行也涵蓋每一次重連。
    vi.stubGlobal('EventSource', FakeEventSource)
    const { invalidate, source } = mount()

    source.emit('open', '')

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jobs'] })
  })

  it('收到一筆就讓 `jobs` 失效——推播是提示，真相仍然在後端', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const { invalidate, source } = mount()

    source.emit('job', JSON.stringify({ hash: 'abc', state: 'downloading', progress: 0.25 }))

    // `['jobs']` 是前綴，所以同一次失效也涵蓋展開中那一列的時間線。
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jobs'] })
  })

  it('認不得的 payload 靜靜忽略，不讓整頁白掉', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const { invalidate, source } = mount()

    source.emit('job', 'not json at all')
    source.emit('job', JSON.stringify({ state: 'downloading' }))

    expect(invalidate).not.toHaveBeenCalled()
  })

  it('元件收起來時連線一定關掉——沒收的連線在後端是一個還在被寫入的佇列', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const { view, source } = mount()

    view.unmount()

    expect(source.closed).toBe(true)
  })

  it('沒有 EventSource 的環境不開連線，也不丟例外', () => {
    vi.stubGlobal('EventSource', undefined)
    const client = new QueryClient()

    expect(() =>
      renderHook(() => useJobStream(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={client}>{children}</QueryClientProvider>
        ),
      }),
    ).not.toThrow()
    expect(FakeEventSource.opened).toHaveLength(0)
  })
})

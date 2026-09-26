import { renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { COALESCE_MS, useJobStream } from './events'
import { deletionQueryOptions, jobQueryOptions, jobsQueryOptions } from './jobs'

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
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const HASH = 'a'.repeat(40)
const OTHER = 'b'.repeat(40)
const LIST = 'GET /api/jobs?filter=active&page=1'
const DELETION = `GET /api/jobs/${HASH}/deletion`

/** 一則推播，照後端 `JobSignalOut` 的形狀。 */
function signal(hash: string, progress = 0.5): string {
  return JSON.stringify({ hash, state: 'downloading', progress })
}

/** 真的掛一份清單（或別的 query）在推播底下，數它打了幾次後端。 */
function mountWith(useWatched: () => unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  renderHook(
    () => {
      useJobStream()
      return useWatched()
    },
    {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  )
  return FakeEventSource.opened.at(-1) as FakeEventSource
}

function calls(stub: ReturnType<typeof stubApi>, path: string): number {
  return stub.mock.calls.filter(([input]) => `GET ${String(input)}` === path).length
}

describe('job 推播', () => {
  it('連上的那一刻先重問一次——訂閱之前推出去的那幾筆誰都收不到', () => {
    // 實跑當場踩到的：送單後那一筆在頁面還在連線時就完成了，於是畫面停在
    // 「已取得檔案清單」再也不動。同一行也涵蓋每一次重連。
    vi.stubGlobal('EventSource', FakeEventSource)
    const { invalidate, source } = mount()

    source.emit('open', '')

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jobs'] })
  })

  it('收到一筆就讓清單與那一筆失效——推播是提示，真相仍然在後端', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('EventSource', FakeEventSource)
    const { invalidate, source } = mount()

    source.emit('job', signal(HASH))
    await vi.advanceTimersByTimeAsync(COALESCE_MS)

    // 那一筆的前綴涵蓋它的詳情、時間線與計劃；進行中的請求不取消（`cancelRefetch: false`）。
    expect(invalidate).toHaveBeenCalledWith(
      { queryKey: ['jobs', 'list'] },
      { cancelRefetch: false },
    )
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['jobs', HASH] }, { cancelRefetch: false })
  })

  describe('一批推播合併成一次重抓（M4 票 04）', () => {
    it('一秒內 20 個事件只重抓一次清單', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('EventSource', FakeEventSource)
      const stub = stubApi({ [LIST]: { body: { jobs: [] } } })
      const source = mountWith(() => useQuery(jobsQueryOptions('active', 1)))
      await vi.waitFor(() => expect(calls(stub, LIST)).toBe(1))

      for (let index = 0; index < 20; index++) {
        source.emit('job', signal(index % 2 ? HASH : OTHER, index / 20))
        await vi.advanceTimersByTimeAsync(45)
      }
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 3)

      expect(calls(stub, LIST)).toBe(2)
    })

    it('單一事件仍會重抓', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('EventSource', FakeEventSource)
      const stub = stubApi({ [LIST]: { body: { jobs: [] } } })
      const source = mountWith(() => useQuery(jobsQueryOptions('active', 1)))
      await vi.waitFor(() => expect(calls(stub, LIST)).toBe(1))

      source.emit('job', signal(HASH))
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 3)

      expect(calls(stub, LIST)).toBe(2)
    })

    it('清單還在抓的時候到的事件，等它回來再重抓一次——不取消它，也不丟掉這一批', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('EventSource', FakeEventSource)
      let answer: () => void = () => {}
      const stub = stubApi({
        [LIST]: () =>
          calls(stub, LIST) === 2
            ? new Promise((resolve) => (answer = () => resolve({ body: { jobs: [] } })))
            : { body: { jobs: [] } },
      })
      const source = mountWith(() => useQuery(jobsQueryOptions('active', 1)))
      await vi.waitFor(() => expect(calls(stub, LIST)).toBe(1))
      source.emit('job', signal(HASH))
      await vi.advanceTimersByTimeAsync(COALESCE_MS)
      expect(calls(stub, LIST)).toBe(2)

      // 第二次還沒回來時又到一批：它說的可能比那一次新。
      source.emit('job', signal(HASH, 0.9))
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 2)
      expect(calls(stub, LIST)).toBe(2)
      answer()
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 2)

      expect(calls(stub, LIST)).toBe(3)
    })

    it('那一筆的詳情還在抓時到的推播也不丟：等它回來再重抓', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('EventSource', FakeEventSource)
      const DETAIL = `GET /api/jobs/${HASH}`
      let answer: () => void = () => {}
      const stub = stubApi({
        [DETAIL]: () =>
          calls(stub, DETAIL) === 2
            ? new Promise((resolve) => (answer = () => resolve({ body: {} })))
            : { body: {} },
      })
      const source = mountWith(() => useQuery(jobQueryOptions(HASH)))
      await vi.waitFor(() => expect(calls(stub, DETAIL)).toBe(1))
      source.emit('job', signal(HASH))
      await vi.advanceTimersByTimeAsync(COALESCE_MS)
      expect(calls(stub, DETAIL)).toBe(2)

      source.emit('job', signal(HASH, 0.9))
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 2)
      answer()
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 2)

      expect(calls(stub, DETAIL)).toBe(3)
    })

    it('刪除對話框開著時，別的 Job 的事件不讓估算重跑——它每跑一次就逐檔 stat', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('EventSource', FakeEventSource)
      const stub = stubApi({ [DELETION]: { body: {} } })
      const source = mountWith(() => useQuery(deletionQueryOptions(HASH, true)))
      await vi.waitFor(() => expect(calls(stub, DELETION)).toBe(1))

      for (let index = 0; index < 5; index++) source.emit('job', signal(OTHER, index / 5))
      await vi.advanceTimersByTimeAsync(COALESCE_MS * 3)

      expect(calls(stub, DELETION)).toBe(1)
    })
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

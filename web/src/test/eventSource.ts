/**
 * jsdom 沒有 `EventSource`，要測推播的測試自己 `vi.stubGlobal('EventSource', FakeEventSource)`——
 * 沒有這個替身的測試照樣畫得出下載列表，「沒有 EventSource 的環境不該爆掉」因此自然成立。
 */
export class FakeEventSource {
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

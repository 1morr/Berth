import { vi } from 'vitest'

/** 把 fetch 換成固定回一份 JSON，回傳 mock 以便斷言呼叫到的網址。 */
export function stubJsonResponse(body: unknown, status = 200) {
  // 標成 typeof fetch，mock.calls 才有 fetch 的參數型別可以斷言。
  const stub = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', stub)
  return stub
}

export const HEALTHY = { status: 'ok', version: '0.1.0' }

import { vi } from 'vitest'

/** 把 fetch 換成固定回一份 JSON，回傳 mock 以便斷言呼叫到的網址。 */
export function stubJsonResponse(body: unknown, status = 200) {
  // 標成 typeof fetch，mock.calls 才有 fetch 的參數型別可以斷言。
  const stub = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', stub)
  return stub
}

export interface StubRoute {
  status?: number
  body: unknown
}

/**
 * 依路徑分派的 fetch 替身。精靈一頁會打好幾支 API，一份固定回應不夠用。
 * key 是 `GET /api/setup/status` 這種 `<method> <path>`；找不到就回 404。
 */
export function stubApi(routes: Record<string, StubRoute | (() => StubRoute)>) {
  const stub = vi.fn<typeof fetch>(async (input, init) => {
    const method = init?.method ?? 'GET'
    const path = typeof input === 'string' ? input : String(input)
    const route = routes[`${method} ${path}`]
    if (!route) return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })
    const resolved = typeof route === 'function' ? route() : route
    return new Response(JSON.stringify(resolved.body), { status: resolved.status ?? 200 })
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

export const HEALTHY = { status: 'ok', version: '0.1.0' }

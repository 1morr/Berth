import { vi } from 'vitest'

import type { Me } from '../api/auth'

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
/** `stubApi` 的路由表：固定回應，或每次叫用時才算的替身（回 Promise 的能停在半路或丟出送不到）。 */
export type StubRoutes = Record<string, StubRoute | (() => StubRoute | Promise<StubRoute>)>

export function stubApi(routes: StubRoutes) {
  const stub = vi.fn<typeof fetch>(async (input, init) => {
    const method = init?.method ?? 'GET'
    const path = typeof input === 'string' ? input : String(input)
    const route = routes[`${method} ${path}`]
    if (!route) return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })
    // 回 Promise 的替身讓請求停在半路：測「送出中」那一段用得到。
    const resolved = typeof route === 'function' ? await route() : route
    const status = resolved.status ?? 200
    // 204 不能帶 body：`new Response('null', { status: 204 })` 會丟 TypeError，替身自己炸掉、
    // 呼叫端走進失敗分支——票 14 的刪除測試因此從來沒看到過「刪掉了」（票 14a）。
    const body = status === 204 ? null : JSON.stringify(resolved.body)
    return new Response(body, { status })
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

/** 精靈已經跑完的一台。路由守衛讀的是這一支（`setup_completed`）。 */
export const HEALTHY = {
  status: 'ok',
  version: '0.1.0',
  setup_completed: true,
  owner_established: true,
}

/** 還沒設定過的一台：任何頁面都該被導向精靈。 */
export const UNCONFIGURED = { ...HEALTHY, setup_completed: false, owner_established: false }

export const UNAUTHORIZED: StubRoute = { status: 401, body: { detail: 'sign in to use this API' } }

/**
 * 對 Berth 自己的請求沒成的三種，各配畫面該說的那半句（`request.*`，M4 票 89）：原本這三種一律說
 * 「Berth 自己的 API 沒有回應」。給 `it.each` 用，每一格是 `[名字, 路由替身, 那半句]`。
 */
export const REQUEST_FAILURES = [
  [
    '500',
    (): StubRoute => ({ status: 500, body: { detail: 'Internal Server Error' } }),
    /看 berth 容器的 log/,
  ],
  ['401', (): StubRoute => UNAUTHORIZED, /登入已失效：重新登入 Berth/],
  [
    '離線',
    (): Promise<StubRoute> => Promise.reject(new TypeError('Failed to fetch')),
    /沒有回應：它可能沒在跑，或網路斷了/,
  ],
] as const

/**
 * 記得「現在有沒有人登入」的假後端。門禁每一次導航都真的去問 `GET /auth/me`
 * （`routes.tsx` 的 `fetchQuery`），固定回應的替身會讓登入之後立刻又被踢回登入頁。
 */
export function session(initial: Me | null = null) {
  let current = initial
  return {
    /** `GET /api/auth/me` */
    me: (): StubRoute => (current === null ? UNAUTHORIZED : { body: current }),
    /** `POST /api/auth/login` */
    signIn: (me: Me) => (): StubRoute => {
      current = me
      return { body: me }
    },
    /** `POST /api/auth/logout` */
    signOut: (): StubRoute => {
      current = null
      return { status: 204, body: null }
    },
  }
}

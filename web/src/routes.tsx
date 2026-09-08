import type { QueryClient } from '@tanstack/react-query'
import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  isRedirect,
  redirect,
  type ParsedLocation,
} from '@tanstack/react-router'

import { meQueryOptions, type Me } from './api/auth'
import { ApiError } from './api/client'
import { healthQueryOptions } from './api/health'
import { destination } from './auth/destination'
import { AppShell } from './AppShell'
import { HealthPage } from './pages/HealthPage'
import { LoginPage } from './pages/LoginPage'
import { ServiceSettingsPage } from './pages/ServiceSettingsPage'
import { SetupRoute } from './pages/SetupRoute'

export interface RouterContext {
  queryClient: QueryClient
}

interface LoginSearch {
  /** 登入後要回去的站內路徑。 */
  redirect?: string
  /** 是被踢出來的，不是第一次來。false 不寫進網址，第一次來的網址就只是 `/login`。 */
  expired?: boolean
}

// 根路由不畫任何 chrome：精靈與登入都是整頁的，不套 app shell。
const rootRoute = createRootRouteWithContext<RouterContext>()({ component: Outlet })

/**
 * setup 未完成時任何頁面都導向精靈（plan §9.3、票 05 驗收）。
 *
 * 問的是 `GET /health` 而不是 `setup/status`：精靈跑完之後 `setup/*` 只有管理員進得去，
 * 而這個決定必須在**還沒有人登入**時就做得出來（票 07）。
 * 後端連不上時不導向：那是健康問題，該讓目的地自己顯示錯誤，而不是把人丟到精靈。
 */
async function isSetupComplete(queryClient: QueryClient) {
  try {
    return (await queryClient.ensureQueryData(healthQueryOptions)).setup_completed
  } catch (error) {
    if (isRedirect(error)) throw error
    return true
  }
}

/**
 * 目前登入的人。cookie 是 httpOnly 的，只能問後端（票 07）。
 *
 * 三種結果各有各的處置：有人（回它）、401（回 `null`，該導向 `/login`）、
 * 其他錯誤（丟出去，代表後端有問題而不是沒登入）。
 */
async function readSession(queryClient: QueryClient): Promise<Me | null> {
  try {
    // `fetchQuery` 而不是 `ensureQueryData`：後者只要快取裡有值就直接回，**不會重抓**
    // （實測 @tanstack/query-core 5.102）。門禁靠它的話，session 在使用中失效之後
    // 每一次前端導航都會拿舊的 `me` 放行，永遠導不到 `/login`。
    return await queryClient.fetchQuery(meQueryOptions)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      // 別讓頁首繼續顯示一個已經失效的人。
      queryClient.removeQueries({ queryKey: meQueryOptions.queryKey })
      return null
    }
    throw error
  }
}

/**
 * 沒有 session 就導向 `/login`。回 `null` 代表問不到後端——那是健康問題，
 * 讓目的地自己顯示錯誤，不要把人丟到登入頁。
 */
async function requireSession(
  queryClient: QueryClient,
  location: ParsedLocation,
): Promise<Me | null> {
  // 這一輪之前畫面上就有人 → 他是被踢出來的，而不是第一次來。這是唯一分得出來的辦法。
  const wasSignedIn = queryClient.getQueryData(meQueryOptions.queryKey) !== undefined
  let me: Me | null
  try {
    me = await readSession(queryClient)
  } catch (error) {
    if (isRedirect(error)) throw error
    return null
  }
  if (me === null) {
    const search: LoginSearch = { redirect: location.href }
    if (wasSignedIn) search.expired = true
    throw redirect({ to: '/login', search })
  }
  return me
}

/**
 * 精靈跑完之後的每一頁共用的門禁：沒跑完就先去跑，跑完了就要有 session。
 *
 * 精靈那一頁不用它——它在「沒跑完」時是留下來而不是導走，那是相反的分支。
 */
async function requireSignedInPage(
  queryClient: QueryClient,
  location: ParsedLocation,
): Promise<Me | null> {
  if (!(await isSetupComplete(queryClient))) throw redirect({ to: '/setup' })
  return await requireSession(queryClient, location)
}

/** 現在有人登入嗎。問不到後端時當成沒有——那時該讓他看得到登入表單。 */
async function signedIn(queryClient: QueryClient): Promise<boolean> {
  try {
    return (await readSession(queryClient)) !== null
  } catch {
    return false
  }
}

interface SetupSearch {
  /**
   * 直接跳到某一個泊位（1–4）。設定跑完之後精靈就是設定入口（plan §6），
   * 而「我的 qBittorrent 密碼改了」的人要的是泊位 2，不是從第 1 步重走。
   */
  berth?: number
}

const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/setup',
  validateSearch: (search: Record<string, unknown>): SetupSearch => {
    const berth = Number(search.berth)
    return Number.isInteger(berth) && berth >= 1 && berth <= 4 ? { berth } : {}
  },
  /**
   * 精靈跑完之前匿名開放——那時候還沒有人登入得了。跑完之後它就是設定入口，
   * 只有管理員進得來（票 07，後端同時回 403）。
   */
  beforeLoad: async ({ context, location }) => {
    if (!(await isSetupComplete(context.queryClient))) return
    const me = await requireSession(context.queryClient, location)
    if (me !== null && me.role !== 'admin') throw redirect({ to: '/' })
  },
  component: SetupRoute,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  validateSearch: (search: Record<string, unknown>): LoginSearch => {
    const parsed: LoginSearch = {}
    if (typeof search.redirect === 'string') parsed.redirect = search.redirect
    if (search.expired === true || search.expired === 'true') parsed.expired = true
    return parsed
  },
  beforeLoad: async ({ context, search }) => {
    // 精靈還沒跑完就還沒有身分來源，這一頁不該存在。
    if (!(await isSetupComplete(context.queryClient))) throw redirect({ to: '/setup' })
    // 已經登入的人不必再看一次表單。
    if (await signedIn(context.queryClient)) throw redirect({ href: destination(search.redirect) })
  },
  component: LoginPage,
})

/**
 * 首頁在 M1 是探索頁（plan §7）。在那之前唯一有內容的頁面是健康頁，所以 `/` 先導到它——
 * 兩個網址畫同一頁比一個轉址難解釋得多。
 */
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/health' })
  },
})

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/health',
  /** 診斷是唯讀資訊，一般使用者也看得到（brief §11）。動作在 `/settings/services`。 */
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: () => (
    <AppShell>
      <HealthPage />
    </AppShell>
  ),
})

const serviceSettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/services',
  /** 改設定是管理員的事（brief §11，後端同時回 403）。 */
  beforeLoad: async ({ context, location }) => {
    const me = await requireSignedInPage(context.queryClient, location)
    if (me !== null && me.role !== 'admin') throw redirect({ to: '/health' })
  },
  component: () => (
    <AppShell>
      <ServiceSettingsPage />
    </AppShell>
  ),
})

export const routeTree = rootRoute.addChildren([
  indexRoute,
  healthRoute,
  loginRoute,
  serviceSettingsRoute,
  setupRoute,
])

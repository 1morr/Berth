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
import { inventoriesQueryOptions, type WallSearch } from './api/inventory'
import { destination } from './auth/destination'
import { AppShell } from './AppShell'
import { DiscoverPage } from './pages/DiscoverPage'
import { HealthPage } from './pages/HealthPage'
import { IssuesPage } from './pages/IssuesPage'
import { ReviewPage } from './pages/ReviewPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { JobsPage } from './pages/JobsPage'
import { InventoryPage, type InventoryFilter } from './pages/InventoryPage'
import { InventoryPageRoute } from './pages/InventoryPageRoute'
import { LoginPage } from './pages/LoginPage'
import { MediaRoute } from './pages/MediaRoute'
import { RouteSettingsPage } from './pages/RouteSettingsPage'
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

/**
 * 健康頁的 search。`denied` 是「你剛剛被擋下來了」——一般使用者按到 `/settings/*` 的深連結時
 * 換了一頁，畫面總要說出為什麼（票 03 第 14 條）。形狀照登入頁的 `expired` 那一條慣例。
 */
interface HealthSearch {
  denied?: boolean
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
 * 首頁是探索頁（plan §7、票 03）。票 10 的「先導向 `/health`」到此為止——Berth 平常
 * 是找東西的地方，不是看它有沒有壞的地方。
 */
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: () => (
    <AppShell>
      <DiscoverPage />
    </AppShell>
  ),
})

/**
 * Media 詳情 `/media/:id`（票 04）。探索牆的每一格連到這裡。
 *
 * `mediaId` 是 `tv:120089` / `movie:1241982`——冒號在路徑段裡是合法字元，而認不得的字串
 * 由後端回一個 `not_found` 的理由，不是 404 頁：使用者手打錯網址時該看到「TMDB 上沒有
 * 這部作品」加一條回探索頁的路，而不是一片空白。
 */
const mediaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/media/$mediaId',
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: MediaRoute,
})

/**
 * 媒體庫 `/library`（票 13、M1.5 票 03）：直接落在第一個媒體庫——這位使用者在 Jellyfin 排在最前面的那一個。
 *
 * 一個都沒有、問不到後端或問不到 Jellyfin 時留在這裡，由頁面自己說原因與下一步——導向一個不存在的
 * id 只會多一次 404。
 */
const inventoryIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/library',
  beforeLoad: async ({ context, location }) => {
    if ((await requireSignedInPage(context.queryClient, location)) === null) return
    try {
      const libraries = await context.queryClient.fetchQuery(inventoriesQueryOptions)
      const first = libraries[0]
      if (first) throw redirect({ to: '/library/$libraryId', params: { libraryId: first.id } })
    } catch (error) {
      if (isRedirect(error)) throw error
    }
  },
  component: () => (
    <AppShell>
      <InventoryPage libraryId={null} page={1} />
    </AppShell>
  ),
})

interface InventorySearch extends WallSearch {
  /** 第幾頁（1 起算）。第 1 頁不寫進網址。 */
  page?: number
  /** 待審 / Unmatched。沒帶就是全部——`false` 與空字串一樣不寫進網址。 */
  filter?: InventoryFilter
}

/**
 * 網址上的類型或年份（M1.5 票 06）。一個值或一串都收（`?years=2020` 被解析成數字，不是陣列），
 * 去掉重複並排好：勾選的先後不同，網址與快取鍵仍是同一個。
 */
function listOf<T extends string | number>(value: unknown, keep: (item: unknown) => item is T) {
  const items = (Array.isArray(value) ? value : [value]).filter(keep)
  return [...new Set(items)].sort((a, b) =>
    typeof a === 'number' && typeof b === 'number' ? a - b : String(a) < String(b) ? -1 : 1,
  )
}

const isGenre = (item: unknown): item is string => typeof item === 'string' && item !== ''
const isYear = (item: unknown): item is number => Number.isInteger(item)

/**
 * 一個 Jellyfin 媒體庫的牆（M1.5 票 03，取代票 13 的 `/library/:routeSlug`）。瀏覽不是管理動作，
 * 一般使用者也進得來（brief §11）；看得到哪幾個媒體庫由後端對 Jellyfin 的允許清單決定。
 */
const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/library/$libraryId',
  validateSearch: (search: Record<string, unknown>): InventorySearch => {
    const parsed: InventorySearch = {}
    const page = Number(search.page)
    if (Number.isInteger(page) && page > 1) parsed.page = page
    if (search.filter === 'review' || search.filter === 'unmatched') parsed.filter = search.filter
    // 排序鍵只認形狀：選單是每個媒體庫自己的，頁面拿到媒體庫之後才對（`wallQuery`）。
    if (typeof search.sort === 'string' && search.sort !== '') parsed.sort = search.sort
    if (search.order === 'Descending') parsed.order = search.order
    const genres = listOf(search.genres, isGenre)
    if (genres.length > 0) parsed.genres = genres
    const years = listOf(search.years, isYear)
    if (years.length > 0) parsed.years = years
    return parsed
  },
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: InventoryPageRoute,
})

/**
 * 下載列表 `/jobs`（票 09）。送單之後去的地方。
 *
 * 一般使用者也進得來：送單本來就是他做的事（brief §11），而這一頁是它的結果。
 */
const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/jobs',
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: () => (
    <AppShell>
      <JobsPage />
    </AppShell>
  ),
})

/**
 * Job 詳情 `/jobs/:hash`（M2 票 12）。守衛與 `/jobs` 相同：一般使用者也進得來，他看得到自己的下載
 * （brief §11）；頁上哪幾顆動作給誰由頁面決定，擋住的那一條在後端的門禁。
 *
 * 認不得的 hash 由頁面畫空狀態（後端回 404），不是路由層的 404 頁——貼錯網址的人要看到的是
 * 「可能打錯了，或已經刪除並清除紀錄」加一條回下載列表的路。
 */
const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/jobs/$hash',
  beforeLoad: async ({ context, location }) => {
    await requireSignedInPage(context.queryClient, location)
  },
  component: function JobDetailRoute() {
    const { hash } = jobDetailRoute.useParams()
    return (
      <AppShell>
        <JobDetailPage hash={hash} />
      </AppShell>
    )
  },
})

/**
 * 待處理 `/issues`（M2 票 05）。
 *
 * **只有管理員**（plan §6，2026-09-22 拍板）：修正與對帳都是 admin 的事。後端的規則在門禁
 * （`api/gate.py` 的 `ADMIN_PREFIXES`），這裡的導向只是讓一般使用者不必看到一頁 403——
 * 前端隱藏不是安全機制。
 */
const issuesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/issues',
  beforeLoad: async ({ context, location }) => {
    const me = await requireSignedInPage(context.queryClient, location)
    if (me !== null && me.role !== 'admin')
      throw redirect({ to: '/health', search: { denied: true } })
  },
  component: () => (
    <AppShell>
      <IssuesPage />
    </AppShell>
  ),
})

/**
 * 審核佇列 `/review`（M2 票 06）。與 `/issues` 同一個規則：**只有管理員**（plan §6、brief §11）。
 * `user` 停在待審核的下載只能等，那一句話在 `/jobs` 與 Media 詳情，不在這裡。
 */
const reviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/review',
  beforeLoad: async ({ context, location }) => {
    const me = await requireSignedInPage(context.queryClient, location)
    if (me !== null && me.role !== 'admin')
      throw redirect({ to: '/health', search: { denied: true } })
  },
  component: () => (
    <AppShell>
      <ReviewPage />
    </AppShell>
  ),
})

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/health',
  validateSearch: (search: Record<string, unknown>): HealthSearch =>
    search.denied === true || search.denied === 'true' ? { denied: true } : {},
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

/**
 * `/settings` 本身沒有頁面，落在第一個分頁（票 14a）。頁首的「設定」連到這裡，所以兩個設定頁上
 * 它都是當前頁；守衛由目的地那一頁自己做。
 */
const settingsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  beforeLoad: () => {
    throw redirect({ to: '/settings/services' })
  },
})

const serviceSettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/services',
  /** 改設定是管理員的事（brief §11，後端同時回 403）。 */
  beforeLoad: async ({ context, location }) => {
    const me = await requireSignedInPage(context.queryClient, location)
    if (me !== null && me.role !== 'admin')
      throw redirect({ to: '/health', search: { denied: true } })
  },
  component: () => (
    <AppShell>
      <ServiceSettingsPage />
    </AppShell>
  ),
})

/**
 * Route 設定頁（票 14）。改 Route 是管理員的事（brief §11）；後端的規則在門禁，
 * 這裡的導向只是讓一般使用者不必看到一頁 403。
 */
const routeSettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/routes',
  beforeLoad: async ({ context, location }) => {
    const me = await requireSignedInPage(context.queryClient, location)
    if (me !== null && me.role !== 'admin')
      throw redirect({ to: '/health', search: { denied: true } })
  },
  component: () => (
    <AppShell>
      <RouteSettingsPage />
    </AppShell>
  ),
})

export const routeTree = rootRoute.addChildren([
  indexRoute,
  healthRoute,
  issuesRoute,
  reviewRoute,
  jobsRoute,
  jobDetailRoute,
  inventoryIndexRoute,
  inventoryRoute,
  loginRoute,
  mediaRoute,
  routeSettingsRoute,
  serviceSettingsRoute,
  settingsIndexRoute,
  setupRoute,
])

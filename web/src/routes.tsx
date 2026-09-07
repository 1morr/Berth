import type { QueryClient } from '@tanstack/react-query'
import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  isRedirect,
  redirect,
} from '@tanstack/react-router'

import { setupStatusQueryOptions } from './api/setup'
import { AppShell } from './AppShell'
import { HealthPage } from './pages/HealthPage'
import { SetupPage } from './pages/SetupPage'

export interface RouterContext {
  queryClient: QueryClient
}

// 根路由不畫任何 chrome：精靈是整頁的，不套 app shell。
const rootRoute = createRootRouteWithContext<RouterContext>()({ component: Outlet })

/**
 * setup 未完成時任何頁面都導向精靈（plan §9.3、票 05 驗收）。
 * 後端連不上時不導向：那是健康問題，該讓目的地自己顯示錯誤，而不是把人丟到精靈。
 */
async function requireSetupComplete({ context }: { context: RouterContext }) {
  let completed = true
  try {
    completed = (await context.queryClient.ensureQueryData(setupStatusQueryOptions)).completed
  } catch (error) {
    if (isRedirect(error)) throw error
  }
  if (!completed) throw redirect({ to: '/setup' })
}

const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/setup',
  component: SetupPage,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: requireSetupComplete,
  component: () => (
    <AppShell>
      <HealthPage />
    </AppShell>
  ),
})

export const routeTree = rootRoute.addChildren([indexRoute, setupRoute])

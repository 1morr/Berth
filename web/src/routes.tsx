import { createRootRoute, createRoute } from '@tanstack/react-router'

import { AppShell } from './AppShell'
import { HealthPage } from './pages/HealthPage'

const rootRoute = createRootRoute({ component: AppShell })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HealthPage,
})

export const routeTree = rootRoute.addChildren([indexRoute])

import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'

import '../i18n'
import { createAppRouter } from '../router'

/** 每個測試給一個新的 QueryClient；關掉重試，失敗的查詢才會立刻反映在畫面上。 */
function newQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

/** 只掛資料層，用來單獨測一個元件。以 `wrapper` 掛，`rerender` 換掉元件時資料層還在。 */
export function renderWithProviders(ui: ReactElement) {
  const client = newQueryClient()
  return render(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })
}

/** 掛真正的 route tree，用來測 shell 與路由有沒有接好。 */
export function renderApp(initialPath = '/') {
  const queryClient = newQueryClient()
  const router = createAppRouter(
    queryClient,
    createMemoryHistory({ initialEntries: [initialPath] }),
  )

  return {
    router,
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  }
}

/**
 * 把一頁掛在一個只有它與首頁的路由上：頁面讀網址、換網址（精靈的 `?step=N`，M4 票 30），但不必替
 * 真正的路由守衛把 `/health` 與 `/auth/me` 都接上。`path` 帶 search 就是從那一頁打開。
 */
export function renderInRoute(ui: ReactElement, path = '/setup') {
  const queryClient = newQueryClient()
  const root = createRootRoute({ component: Outlet })
  const page = createRoute({
    getParentRoute: () => root,
    path: new URL(path, 'http://berth.test').pathname,
    component: () => ui,
  })
  const home = createRoute({ getParentRoute: () => root, path: '/', component: () => null })
  const router = createRouter({
    routeTree: root.addChildren([page, home]),
    history: createMemoryHistory({ initialEntries: [path] }),
  })

  return {
    router,
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  }
}

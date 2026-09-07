import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router'
import { render } from '@testing-library/react'

import '../i18n'
import { routeTree } from '../routes'

/** 每個測試給一個新的 QueryClient；關掉重試，失敗的查詢才會立刻反映在畫面上。 */
function newQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

/** 只掛資料層，用來單獨測一個元件。 */
export function renderWithProviders(ui: ReactElement) {
  return render(<QueryClientProvider client={newQueryClient()}>{ui}</QueryClientProvider>)
}

/** 掛真正的 route tree，用來測 shell 與路由有沒有接好。 */
export function renderApp(initialPath = '/') {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  })

  return render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

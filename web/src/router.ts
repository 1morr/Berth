import { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'

import { routeTree } from './routes'

/** 每個查詢一個新的 client；路由守衛（routes.tsx）要用它讀 setup 狀態。 */
export function createQueryClient() {
  return new QueryClient()
}

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({ routeTree, context: { queryClient }, history })
}

export const queryClient = createQueryClient()
export const router = createAppRouter(queryClient)

// 少了這段，Link 與 useNavigate 就沒有路徑的型別檢查。
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

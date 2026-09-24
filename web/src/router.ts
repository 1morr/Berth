import { QueryClient, hashKey } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'

import { meQueryOptions, SIGN_IN_KEY } from './api/auth'
import { signedOut } from './api/client'
import { routeTree } from './routes'

/**
 * 每個查詢一個新的 client；路由守衛（routes.tsx）要用它讀 setup 狀態。
 *
 * 預設重試三次（TanStack 的預設）但 **401 不重試**：session 結束了重試不會好，而三次退避是七秒，
 * 這七秒裡畫面停在一頁什麼都做不了的樣子（M3 票 06 code-review 抓到）。
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: (failures, error) => !signedOut(error) && failures < 3 },
    },
  })
}

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  const router = createRouter({ routeTree, context: { queryClient }, history })
  leaveOnSignOut(queryClient, () => void router.invalidate())
  return router
}

/**
 * 任何請求回 401 就重跑路由守衛（M3 票 06）：守衛問 `GET /auth/me` 拿到 401，把人送到
 * `/login?redirect=<這一頁>` 並說「登入已失效」，登入之後回到這一頁——與 session 在兩次導航之間過期同一條路。
 *
 * 掛在快取上而不是 `api/client.ts`：那一層不認得路由，而每一個讀資料與按鈕都經過這兩份快取。
 * 例外兩支：`GET /auth/me` 的 401 本來就由守衛處置（再重跑一次會繞圈），登入的 401 是帳密不對。
 */
function leaveOnSignOut(queryClient: QueryClient, rerunGuards: () => void) {
  const me = hashKey(meQueryOptions.queryKey)
  const login = hashKey(SIGN_IN_KEY)

  queryClient.getQueryCache().subscribe((event) => {
    if (event.type !== 'updated' || event.action.type !== 'error') return
    if (event.query.queryHash === me) return
    if (signedOut(event.action.error)) rerunGuards()
  })
  queryClient.getMutationCache().subscribe((event) => {
    if (event.type !== 'updated' || event.action.type !== 'error') return
    const key = event.mutation.options.mutationKey
    if (key && hashKey(key) === login) return
    if (signedOut(event.action.error)) rerunGuards()
  })
}

export const queryClient = createQueryClient()
export const router = createAppRouter(queryClient)

// 少了這段，Link 與 useNavigate 就沒有路徑的型別檢查。
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

import { createRouter } from '@tanstack/react-router'

import { routeTree } from './routes'

export const router = createRouter({ routeTree })

// 少了這段，Link 與 useNavigate 就沒有路徑的型別檢查。
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

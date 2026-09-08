import { useSearch } from '@tanstack/react-router'

import { SetupPage } from './SetupPage'

/**
 * `/setup` 的路由層：把 `?berth=N` 讀出來交給頁面。
 *
 * 兩件事各有各的家。`useSearch` 只有在 router 底下才成立，而 `SetupPage` 的元件測試刻意
 * 不掛 router（`test/render.tsx` 的 `renderWithProviders`）；`routes.tsx` 又不能同時匯出
 * `routeTree` 與一個元件（react-refresh 只在整個檔案都是元件時才運作，票 07 的
 * `auth/destination.ts` 是同一條規則的另一面）。所以這一層薄的包裝自己一個檔案。
 */
export function SetupRoute() {
  const { berth } = useSearch({ from: '/setup' })
  return <SetupPage berth={berth} />
}

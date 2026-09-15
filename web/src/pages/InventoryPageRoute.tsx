import { useParams, useSearch } from '@tanstack/react-router'

import { AppShell } from '../AppShell'
import { InventoryPage } from './InventoryPage'

/** `/library/$routeSlug` 的路由層：把路徑段與篩選讀出來交給頁面（`MediaRoute` 是同一個道理）。 */
export function InventoryPageRoute() {
  const { routeSlug } = useParams({ from: '/library/$routeSlug' })
  const { filter } = useSearch({ from: '/library/$routeSlug' })
  return (
    <AppShell>
      <InventoryPage slug={routeSlug} filter={filter} />
    </AppShell>
  )
}

import { useParams, useSearch } from '@tanstack/react-router'

import { AppShell } from '../AppShell'
import { InventoryPage } from './InventoryPage'

/** `/library/$libraryId` 的路由層：把路徑段、頁碼與篩選讀出來交給頁面（`MediaRoute` 是同一個道理）。 */
export function InventoryPageRoute() {
  const { libraryId } = useParams({ from: '/library/$libraryId' })
  const { page, filter, ...search } = useSearch({ from: '/library/$libraryId' })
  return (
    <AppShell>
      <InventoryPage libraryId={libraryId} page={page ?? 1} filter={filter} search={search} />
    </AppShell>
  )
}

import { useParams } from '@tanstack/react-router'

import { AppShell } from '../AppShell'
import { MediaDetailPage } from './MediaDetailPage'

/**
 * `/media/$mediaId` 的路由層：把路徑段讀出來交給頁面（`SetupRoute` 是同一個道理）。
 *
 * `mediaId` 是 `tv:120089` 這種複合鍵。冒號在網址裡會被編碼成 `%3A`，`useParams` 解回原樣。
 */
export function MediaRoute() {
  const { mediaId } = useParams({ from: '/media/$mediaId' })
  return (
    <AppShell>
      <MediaDetailPage id={mediaId} />
    </AppShell>
  )
}

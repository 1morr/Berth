import type { JellyfinSetup, LibraryDraft, RouteSetup } from '../api/setup'
import { checking } from '../components/routeChecks'

/**
 * 頁 3 套件內進頁就自動建立並檢查嗎（M4 票 43，brief §19 D7，`.scratch/m4/route-auto-run-shape.md`）。
 *
 * **只在什麼都還沒做時**：清單是預設那三列、一個都還沒建、一條 Route 都沒有、建媒體庫那一步從沒跑過、
 * 版本夠新。跑過一次（哪怕紅了）之後一律回到按鍵：重新整理、回到這一頁都不再自動寫入。既有 Jellyfin
 * 照舊按鍵（票 08）。這一頁做完了沒由呼叫端另外看。
 */
export function startsOnItsOwn(jellyfin: JellyfinSetup, routes: RouteSetup): boolean {
  return (
    jellyfin.origin === 'bundled' &&
    routes.origin === 'bundled' &&
    jellyfin.bundled_default &&
    jellyfin.version_supported &&
    routes.routes.length === 0 &&
    !jellyfin.bundled.some((row) => row.built) &&
    !jellyfin.steps.some((row) => row.step === 'libraries' && row.status !== 'pending')
  )
}

/** 存下來的清單照原樣送回去：自動那一次沒有草稿可讀，送的就是伺服器上那一份。 */
export function storedList(jellyfin: JellyfinSetup): LibraryDraft[] {
  return jellyfin.bundled.map(({ name, collection_type, folder }) => ({
    name,
    collection_type,
    folder,
  }))
}

/*
 * 伺服器說還有東西在跑（每一步、每一條纜繩開跑前寫 `running`）。頁 3 照它輪詢——跑到一半重新整理時，
 * 這一頁沒有送出中的請求，靠它接得上進度。
 */

/** 建媒體庫那一步還在跑。 */
export function librariesRunning(jellyfin: JellyfinSetup | undefined): boolean {
  return (
    jellyfin?.steps.some((row) => row.step === 'libraries' && row.status === 'running') ?? false
  )
}

/** 某條 Route 的某條纜繩還在跑。 */
export function routesRunning(routes: RouteSetup | undefined): boolean {
  return routes?.routes.some(checking) ?? false
}

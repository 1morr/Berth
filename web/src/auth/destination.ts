import type { QueryClient } from '@tanstack/react-query'

import { inventoriesQueryOptions } from '../api/inventory'

const PROTOCOL_RELATIVE = ['//', '/\\']

/**
 * 沒有指定去處時落在哪裡（brief §19）。Berth 入庫過東西的人落在媒體庫：接著看的兩列只在那裡
 * （2026-09-24，M3 票 06），`/library` 自己再落到這個人的第一個媒體庫。媒體庫裡還一筆都沒有時
 * 落在探索（2026-09-26）：精靈剛跑完、或接上的是別人的 Jellyfin 時，媒體庫是一面空牆或別人的片，
 * 第一件事是找片。
 */
export function home(hasImports: boolean): string {
  return hasImports ? '/library' : '/'
}

/**
 * `?redirect=` 裡的站內路徑；不是的話 `undefined`。它來自網址列，所以只收站內路徑——少了這道
 * 檢查，一條 `?redirect=https://…` 的連結就能把剛登入的人送到別人的網站去。開頭是 `//` 或 `/\`
 * 的字串瀏覽器都當成通訊協定相對網址，兩種都要擋。
 *
 * **清洗做在這裡而不是路由的 `validateSearch`**：TanStack Router 會把父路由沒宣告的
 * search 參數原樣往下傳，子路由的驗證結果只是疊在上面，刪不掉它（實測 1.171）。
 */
export function internalRedirect(redirect: string | undefined): string | undefined {
  if (redirect === undefined || !redirect.startsWith('/')) return undefined
  return PROTOCOL_RELATIVE.some((prefix) => redirect.startsWith(prefix)) ? undefined : redirect
}

/**
 * 登入後要去哪裡：有站內的去處就回去，沒有才問媒體庫（那一支要繞到 Jellyfin）。
 *
 * 問不到時當成有：媒體庫頁自己說得出 Jellyfin 為什麼答不了，探索頁說不出。**不重試**——登入按鈕
 * 在重試的那幾秒一直停在「登入中」，而媒體庫頁進場時自己會再問一次。
 */
export async function destination(
  queryClient: QueryClient,
  redirect: string | undefined,
): Promise<string> {
  const back = internalRedirect(redirect)
  if (back !== undefined) return back
  try {
    const libraries = await queryClient.fetchQuery({ ...inventoriesQueryOptions, retry: false })
    return home(libraries.some((library) => library.has_imports))
  } catch {
    return home(true)
  }
}

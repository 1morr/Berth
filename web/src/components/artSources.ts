import type { Schemas } from '../api/schemas'

type ImageSize = Schemas['ImageSize']

/** Berth 圖片代理的每一種尺寸有多寬（後端 `services/jellyfin_images.IMAGE_SIZES`）。 */
const PROXY_WIDTHS = {
  poster: 342,
  poster_large: 684,
  wide: 342,
  wide_large: 684,
} as const satisfies Record<ImageSize, number>

/** 卡片上的網址是小的那一張；`srcset` 再給同一個形狀的大一號。 */
const PROXY_LADDER = new Map<string, readonly ImageSize[]>([
  ['poster', ['poster', 'poster_large']],
  ['wide', ['wide', 'wide_large']],
])

/**
 * TMDB 的海報寬度（`configuration` 的 `poster_sizes`）。卡片上的網址是 `w342`（`services/discover.POSTER_SIZE`），
 * 小的那一張給一倍密度的窄格子省流量，大的兩張給高密度螢幕。
 */
const TMDB_WIDTHS = [185, 342, 500, 780] as const
const TMDB_SIZE = /\/t\/p\/w\d+\//

/**
 * 一張圖的 `srcset`（票 13）：網址是後端組的，形狀只有兩種——Berth 代理的 Jellyfin 圖（`?size=` 是具名尺寸）
 * 與 TMDB 的圖（路徑上的 `w342`）。同一張圖換尺寸只換那一段，其餘原樣。
 *
 * 認不得的網址（空字串、別的來源）回 `undefined`：`<img>` 照 `src` 載那一張，不猜。
 */
export function artSrcSet(url: string): string | undefined {
  if (url.startsWith('/api/jellyfin/')) {
    const [path, query = ''] = url.split('?', 2)
    const params = new URLSearchParams(query)
    const ladder = PROXY_LADDER.get(params.get('size') ?? '')
    if (!ladder) return undefined
    return ladder
      .map((size) => {
        params.set('size', size)
        return `${path}?${params} ${PROXY_WIDTHS[size]}w`
      })
      .join(', ')
  }
  if (url.startsWith('https://image.tmdb.org/') && TMDB_SIZE.test(url)) {
    return TMDB_WIDTHS.map(
      (width) => `${url.replace(TMDB_SIZE, `/t/p/w${width}/`)} ${width}w`,
    ).join(', ')
  }
  return undefined
}

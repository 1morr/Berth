import { describe, expect, it } from 'vitest'

import { artSrcSet } from './artSources'

const ITEM = '/api/jellyfin/items/2a9857e656bbd18b7c3c3a3b4ee5eef1/images'
const TAG = 'f99664090dfd3223c18e80663440deac'

describe('artSrcSet（票 13）', () => {
  it('Berth 代理的海報給兩個寬度，只換 size，tag 原樣', () => {
    expect(artSrcSet(`${ITEM}/Primary?size=poster&tag=${TAG}`)).toBe(
      `${ITEM}/Primary?size=poster&tag=${TAG} 342w, ${ITEM}/Primary?size=poster_large&tag=${TAG} 684w`,
    )
  })

  it('橫圖換成橫圖的大一號，不是海報的', () => {
    expect(artSrcSet(`${ITEM}/Thumb?size=wide&tag=${TAG}`)).toBe(
      `${ITEM}/Thumb?size=wide&tag=${TAG} 342w, ${ITEM}/Thumb?size=wide_large&tag=${TAG} 684w`,
    )
  })

  it('TMDB 的海報給四個寬度，只換路徑上的那一段', () => {
    expect(artSrcSet('https://image.tmdb.org/t/p/w342/abc.jpg')).toBe(
      [185, 342, 500, 780]
        .map((width) => `https://image.tmdb.org/t/p/w${width}/abc.jpg ${width}w`)
        .join(', '),
    )
  })

  it.each([
    ['空字串', ''],
    ['代理網址沒有認得的尺寸', `${ITEM}/Primary?size=original&tag=${TAG}`],
    ['別的來源', 'https://example.com/t/p/w342/abc.jpg'],
    ['TMDB 的原圖', 'https://image.tmdb.org/t/p/original/abc.jpg'],
  ])('%s不給 srcset，只照 src 載那一張', (_, url) => {
    expect(artSrcSet(url)).toBeUndefined()
  })
})

import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { artSrcSet } from './artSources'
import { WALL_SIZES } from './wallGrid'

/** 圖位的兩種形狀：牆上與詳情頁的 2:3 海報、接著看與集卡的 16:9 橫圖（後端 `ImageSize` 的小的那一張）。 */
const SHAPES = {
  poster: { box: 'aspect-[2/3]', width: 342, height: 513, missing: 'discover.noArt' },
  wide: { box: 'aspect-video', width: 342, height: 192, missing: 'watching.noArt' },
} as const

/**
 * 一格圖：Berth 代理的 Jellyfin 圖或 TMDB 的海報。網址是空的、或圖載不下來（Jellyfin 回 404、連不上、TMDB
 * 那一端沒有）時同一塊矩形裡印一行「無海報 / 無圖」，格子高度不變，牆不壞（票 04、DESIGN.md Shapes）。
 *
 * **全站只有這一份**（票 13）：牆、接著看、集卡與詳情頁的身分帶都是它。詳情頁那一格原本是另一份
 * `Poster.tsx`，同一段 `onError` 寫了兩次，而 M1.5 票 11 的 audit 抓到的正是其中一份漏了它。外框由呼叫端給
 * （`className`：詳情頁的那一格自己有邊框）。
 *
 * `srcset` 給同一張圖的幾個寬度（`artSrcSet`），`sizes` 說這一格在版面上多寬，瀏覽器照螢幕密度挑——
 * 手機兩欄與高密度螢幕上 342 寬的圖是糊的。`width` / `height` 只給比例，版面在圖到之前就定位。
 *
 * `alt=""`：名稱就在旁邊的標識帶或身分帶上，圖是裝飾性的——給它 alt 只會把同一個名字唸兩次。
 */
export function ArtSlot({
  url,
  shape,
  sizes = WALL_SIZES,
  className = '',
}: {
  url: string
  shape: keyof typeof SHAPES
  /** 這一格在版面上多寬。預設是牆的欄數（`WALL_GRID`）。 */
  sizes?: string
  className?: string
}) {
  const { t } = useTranslation()
  // 記載入失敗的是哪一個網址而不是一個布林值：換頁時同一格換了一張圖，就該重新試。
  const [failed, setFailed] = useState('')
  const { box, width, height, missing } = SHAPES[shape]
  const srcSet = url ? artSrcSet(url) : undefined

  return (
    <div className={`relative ${box} bg-hull ${className}`}>
      {url && url !== failed ? (
        <img
          src={url}
          srcSet={srcSet}
          sizes={srcSet ? sizes : undefined}
          alt=""
          loading="lazy"
          className="size-full object-cover"
          width={width}
          height={height}
          onError={() => setFailed(url)}
        />
      ) : (
        <span className="value absolute inset-0 flex items-center justify-center text-xs text-ink-dim">
          {t(missing)}
        </span>
      )}
    </div>
  )
}

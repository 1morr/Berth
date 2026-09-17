import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/** 圖位的兩種形狀：牆上的 2:3 海報、繼續觀看與下一集的 16:9 橫圖（後端 `ImageSize` 的像素）。 */
const SHAPES = {
  poster: { box: 'aspect-[2/3]', width: 342, height: 513, missing: 'discover.noArt' },
  wide: { box: 'aspect-video', width: 342, height: 192, missing: 'watching.noArt' },
} as const

/**
 * Berth 代理的 Jellyfin 圖。網址是空的、或圖載不下來（Jellyfin 回 404、連不上）時同一塊矩形裡印一行
 * 「無海報 / 無圖」，格子高度不變，牆不壞（票 04、DESIGN.md Shapes）。
 */
export function ArtSlot({ url, shape }: { url: string; shape: keyof typeof SHAPES }) {
  const { t } = useTranslation()
  // 記載入失敗的是哪一個網址而不是一個布林值：換頁時同一格換了一張圖，就該重新試。
  const [failed, setFailed] = useState('')
  const { box, width, height, missing } = SHAPES[shape]

  return (
    <div className={`relative ${box} bg-hull`}>
      {url && url !== failed ? (
        // 名稱就在下面那條標識帶上，圖是裝飾性的——給它 alt 只會把同一個名字唸兩次。
        <img
          src={url}
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

import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * 一格海報（`.scratch/m1/media-detail-shape.md` §6）。
 *
 * 與探索頁的卡片是**同一塊漆**：2:3、零圓角、`well` 底、沒有海報時置中的 `NO ART` 模板字。
 * 尺寸由呼叫端給，因為詳情頁的那一格比牆上的小，但比例不變——`aspect-[2/3]` 讓版面在圖
 * 載入前就定位，不會等圖到齊才跳一次。
 *
 * `alt=""`：標題就在旁邊那一欄，給它 alt 只會讓螢幕閱讀器把同一個名字唸兩次。
 *
 * 載不下來時也印那行字（票 11 的 audit）：這一格畫的是 **TMDB** 的海報，那一端的圖不在或抓不到時，
 * 沒有這一段的話詳情頁會露出瀏覽器的破圖示，而媒體庫牆同樣的情況是「無海報」（`ArtSlot`）。
 * 記的是失敗的那個網址而不是一個布林值——換一部作品就該重新試（與 `ArtSlot` 同一個做法）。
 */
export function Poster({ url, className = '' }: { url: string; className?: string }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState('')

  return (
    <div className={`relative aspect-[2/3] shrink-0 border-2 border-rule bg-well ${className}`}>
      {url && url !== failed ? (
        <img
          src={url}
          alt=""
          className="size-full object-cover"
          width={342}
          height={513}
          onError={() => setFailed(url)}
        />
      ) : (
        <span className="value absolute inset-0 flex items-center justify-center text-xs text-ink-dim">
          {t('discover.noArt')}
        </span>
      )}
    </div>
  )
}

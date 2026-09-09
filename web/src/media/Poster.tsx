import { useTranslation } from 'react-i18next'

/**
 * 一格海報（`.scratch/m1/media-detail-shape.md` §6）。
 *
 * 與探索頁的卡片是**同一塊漆**：2:3、零圓角、`well` 底、沒有海報時置中的 `NO ART` 模板字。
 * 尺寸由呼叫端給，因為詳情頁的那一格比牆上的小，但比例不變——`aspect-[2/3]` 讓版面在圖
 * 載入前就定位，不會等圖到齊才跳一次。
 *
 * `alt=""`：標題就在旁邊那一欄，給它 alt 只會讓螢幕閱讀器把同一個名字唸兩次。
 */
export function Poster({ url, className = '' }: { url: string; className?: string }) {
  const { t } = useTranslation()

  return (
    <div className={`relative aspect-[2/3] shrink-0 border-2 border-rule bg-well ${className}`}>
      {url ? (
        <img src={url} alt="" className="size-full object-cover" width={342} height={513} />
      ) : (
        <span className="value absolute inset-0 flex items-center justify-center text-xs text-ink-dim">
          {t('discover.noArt')}
        </span>
      )}
    </div>
  )
}

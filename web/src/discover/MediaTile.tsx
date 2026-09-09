import { useTranslation } from 'react-i18next'

import type { DiscoverItem } from '../api/discover'

/**
 * 牆上的一格（`.scratch/m1/discover-shape.md` §3）。
 *
 * 海報是貨櫃的塗裝，底下那條標識帶是噴在箱體上的編號——兩層是同一個語彙，不是「圖片加說明文字」。
 * 所以帶子上沒有散文：類型代號、年份、標題、原文標題，全部貼在自己那一行（The Values Sit On
 * Their Line Rule）。
 *
 * **這一票裡它不是連結**：`/media/:id` 要到票 04 才存在，而一個點下去沒反應的格子比一個不能點的
 * 格子更糟。票 04 把整格包成連結時，hover / focus 的處理是邊框由 `rule` 換 `rule-strong`。
 */
export function MediaTile({ item }: { item: DiscoverItem }) {
  const { t } = useTranslation()

  return (
    <article className="grid grid-rows-[auto_1fr] border-2 border-rule bg-well">
      <div className="relative aspect-[2/3] bg-hull">
        {item.poster_url ? (
          // 標題就在下面那一行，所以海報是裝飾性的——給它 alt 只會讓螢幕閱讀器把同一個名字唸兩次。
          <img
            src={item.poster_url}
            alt=""
            loading="lazy"
            className="size-full object-cover"
            width={342}
            height={513}
          />
        ) : (
          <span className="value absolute inset-0 flex items-center justify-center text-xs text-ink-dim">
            {t('discover.noArt')}
          </span>
        )}
      </div>
      <div className="grid content-start gap-1 px-3 py-2.5">
        <p className="flex min-h-6 items-center justify-between gap-2">
          <span className="value text-xs text-ink-dim">
            {KIND_CODE[item.kind]} · {item.year ?? '—'}
          </span>
          {item.tracked && (
            // 中性色塊：追蹤是一段關係，不是健康狀態（The Role Is Not A State Rule）。
            // M2 有了「部分 / 完整 / 下載中」時，四個信號色才有東西可用。
            //
            // **貼在標識帶上而不是壓在海報上**：色塊疊在圖像上時，它讀不讀得出來取決於那張
            // 海報那一角剛好是什麼顏色。實跑量到的就是這件事——`deck` 在亮色主題是近白，
            // 壓在深色海報上很清楚；深色主題它是中灰，壓在深色海報上幾乎消失。
            // 標識帶的底是 `well`，兩個主題都是設計系統保證得了的一組值（11.95:1 / 12.4:1）。
            <span className="label bg-deck px-2 py-1 text-ink">{t('discover.tracked')}</span>
          )}
        </p>
        <p className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">{item.title}</p>
        {item.title_en !== item.title && (
          <p className="value line-clamp-1 text-xs text-ink-dim">{item.title_en}</p>
        )}
      </div>
    </article>
  )
}

/**
 * 類型代號不走 i18n：它與 `BTH 1` 同一個語域——分類代號在哪個語言都是同一串字母
 * （`.scratch/m1/discover-shape.md` §8）。走 `.value` 而不是 `.label`，因為 `.label` 會把
 * 拉丁字母大寫掉，而這兩個字串本來就是大寫的代號，套上去只是多一層會說謊的處理。
 */
const KIND_CODE = { tv: 'TV', movie: 'MOVIE' } as const satisfies Record<
  DiscoverItem['kind'],
  string
>

/** 讀取中的格子：海報位留一個空位，標識帶留兩條線。**不會動**——這個世界沒有骨架屏動畫。 */
export function TilePlaceholder() {
  return (
    <div className="grid grid-rows-[auto_1fr] border-2 border-rule bg-well" aria-hidden="true">
      <div className="aspect-[2/3] bg-hull" />
      <div className="grid content-start gap-2 px-3 py-3.5">
        <span className="block h-2 w-12 bg-deck" />
        <span className="block h-2 w-4/5 bg-deck" />
      </div>
    </div>
  )
}

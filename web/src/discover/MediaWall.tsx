import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Discover } from '../api/discover'
import { TmdbNotice } from '../components/TmdbNotice'
import { MediaTile, TilePlaceholder } from './MediaTile'

/** 讀取中先畫幾格空位。夠填滿桌機第一屏，版面才不會在圖到齊時整個往下跳。 */
const PLACEHOLDERS = 12

/**
 * 一個 feed 的一面牆（`.scratch/m1/discover-shape.md` §6）。
 *
 * 三種結局各有各的樣子，而且**每面牆各自結局**：趨勢拿不到不該讓熱門也變成一片空白，
 * 所以後端逐個 feed 回自己的 `problem`（`api/discover.py` 的 `DiscoverOut`）。
 */
export function MediaWall({
  title,
  result,
  pending,
  empty,
  emptyAction,
  onRetry,
}: {
  title: string
  result: Discover | undefined
  pending: boolean
  /** 沒有結果時說什麼。搜尋與趨勢的空手而歸不是同一句話。 */
  empty: string
  /** 空手而歸時的下一步。搜尋有（回到趨勢），趨勢自己沒有。 */
  emptyAction?: ReactNode
  onRetry: () => void
}) {
  const { t } = useTranslation()
  // 沒有名字的 `section` 不是 landmark，螢幕閱讀器跳不到它，兩面牆聽起來也是同一片。
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {title}
        </h2>
        {result && result.items.length > 0 && (
          // 光一個「40」唸出來是沒有意義的，所以唸的是帶單位的那一句。`aria-label` 掛在 `<p>`
          // 上不可靠（它不是一個有名字的角色），改成看得見的數字 + 只給螢幕閱讀器的句子。
          <p className="value text-xs text-ink-dim">
            <span aria-hidden="true">{result.items.length}</span>
            <span className="sr-only">
              {t('discover.search.count', { count: result.items.length })}
            </span>
          </p>
        )}
      </div>

      {pending ? (
        <Grid>
          {Array.from({ length: PLACEHOLDERS }, (_, index) => (
            <TilePlaceholder key={index} />
          ))}
        </Grid>
      ) : result?.problem ? (
        <TmdbNotice problem={result.problem} detail={result.detail} onRetry={onRetry} />
      ) : result && result.items.length > 0 ? (
        <Grid>
          {result.items.map((item) => (
            <MediaTile key={item.id} item={item} />
          ))}
        </Grid>
      ) : (
        <div className="grid justify-items-start gap-3 py-2">
          <p className="max-w-prose text-sm text-ink-dim">{result ? empty : t('discover.off')}</p>
          {result && emptyAction}
        </div>
      )}
    </section>
  )
}

/**
 * 貨櫃堆場的堆疊圖。窄版兩欄——一欄會讓一屏只看得到一部作品，而這一頁的工作是掃視。
 *
 * 線由每一格自己的 `border-2` 畫，**不是**把整塊網格塗成 `rule` 再用 `gap-px` 透出來
 * （泊位板是那樣做的）。理由是那塊板永遠是四格滿的，而這面牆的格數是 TMDB 給多少算多少：
 * 塗底的話，只搜到一部作品時整排空欄會變成一塊灰色的板子——實跑第一輪就是這個樣子。
 */
function Grid({ children }: { children: React.ReactNode }) {
  return <div className={WALL_GRID}>{children}</div>
}

/**
 * 牆的欄數。媒體庫的牆（票 13）是同一座堆場的盤點表，格子必須與這裡對得齊——
 * 所以斷點只有這一份。
 */
export const WALL_GRID = 'grid grid-cols-2 gap-0 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6'

import type { ComponentProps, ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

import { ArtSlot } from './ArtSlot'

/** 上面那一塊連到哪：Berth 的 Media 詳情，或 Jellyfin 的某一項（新分頁）。 */
export type TileLink = { mediaId: string } | { href: string }

/**
 * 貨櫃的一格，底下多一行控制項：媒體庫牆的卡片（`InventoryTile`）與觀看區的集卡（`WatchArea`）。
 *
 * M2 票 14 把這兩份合成一份（M1.5 critique：四張卡片各自實作，標識帶的節奏要改得改四處）。**只有這一對**：
 * 兩者都是「圖 + 標識帶一塊連結，底下並排一行控制項」。探索牆的 `MediaTile` 整格一條連結、沒有底行，
 * 首頁的 `WatchingTile` 也是；它們共用的是 `ArtSlot`，不是這個外框。
 *
 * 版面在這裡、內容在呼叫端：
 *
 * - 上面那一塊（圖到標識帶最後一行）是**一條**連結，底行在連結外面——**並排不巢狀**（使用者拍板，票 13）。
 *   框的 hover 與焦點用 `has-[a:…]`，底行那條連結也算。沒有連結時那一塊是一段 `div`。
 * - 連結的名字由呼叫端給：作品名，或「S01E04 集名（開新分頁）」——整格的字串起來是「無圖 S01E04 …」，
 *   控制項清單裡每一條都從代號念起（票 13）。標識帶上其餘的行是描述（`describedBy`）。
 * - 底行固定高度（`min-h-10`）、`border-t-2`：同排的卡片基線對得齊，就地確認從這一行展開。
 */
export function Tile({
  url,
  shape,
  link,
  label,
  describedBy,
  children,
  foot,
}: {
  url: string
  shape: ComponentProps<typeof ArtSlot>['shape']
  link: TileLink | null
  label: string
  describedBy?: string
  /** 標識帶的每一行。 */
  children: ReactNode
  foot: ReactNode
}) {
  const body = (
    <>
      <ArtSlot url={url} shape={shape} />
      <div className="grid content-start gap-1 px-3 py-2.5">{children}</div>
    </>
  )
  const block = 'grid grid-rows-[auto_1fr]'

  return (
    <article className="grid h-full grid-rows-[1fr_auto] border-2 border-rule bg-well has-[a:hover]:border-rule-strong has-[a:focus-visible]:border-rule-strong">
      {link === null ? (
        <div className={block}>{body}</div>
      ) : 'mediaId' in link ? (
        <Link
          to="/media/$mediaId"
          params={{ mediaId: link.mediaId }}
          aria-label={label}
          aria-describedby={describedBy}
          className={block}
        >
          {body}
        </Link>
      ) : (
        <a
          href={link.href}
          target="_blank"
          rel="noreferrer"
          aria-label={label}
          aria-describedby={describedBy}
          className={block}
        >
          {body}
        </a>
      )}
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-t-2 border-rule px-3 py-1.5 text-xs">
        {foot}
      </div>
    </article>
  )
}

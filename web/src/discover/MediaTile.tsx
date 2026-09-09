import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { DiscoverItem } from '../api/discover'
import { KIND_CODE } from '../components/kind'

/**
 * 牆上的一格（`.scratch/m1/discover-shape.md` §3）。
 *
 * 海報是貨櫃的塗裝，底下那條標識帶是噴在箱體上的編號——兩層是同一個語彙，不是「圖片加說明文字」。
 * 所以帶子上沒有散文：類型代號、年份、標題、原文標題，全部貼在自己那一行（The Values Sit On
 * Their Line Rule）。
 *
 * **整格是一個連結**（票 04 接手了票 03 留下的那條線）：hover / focus 時邊框由 `rule` 換
 * `rule-strong`——線變重，不是變色，與 GhostButton 同一條規則。整格可點是因為手指點得到的
 * 目標要夠大，而不是只有標題那一行。
 */
export function MediaTile({ item }: { item: DiscoverItem }) {
  const { t } = useTranslation()

  return (
    <Link
      to="/media/$mediaId"
      params={{ mediaId: item.id }}
      className="grid grid-rows-[auto_1fr] border-2 border-rule bg-well hover:border-rule-strong"
    >
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
        {/* **這一格上沒有狀態**（票 04b）：「已追蹤 / 部分 / 完整 / 下載中」要等 Job 與帳本
            才推導得出來（票 09 起，brief §13）。在那之前每一格都會是同一個字，等於沒說。
            色塊回來時它貼在這條標識帶上、不壓在海報上（DESIGN.md 的 The Paint Needs A
            Painted Ground Rule）。 */}
        <p className="value text-xs text-ink-dim">
          {KIND_CODE[item.kind]} · {item.year ?? '—'}
        </p>
        <p className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">{item.title}</p>
        {item.title_en !== item.title && (
          <p className="value line-clamp-1 text-xs text-ink-dim">{item.title_en}</p>
        )}
      </div>
    </Link>
  )
}

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

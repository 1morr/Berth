import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { DiscoverItem } from '../api/discover'
import { ArtSlot } from '../components/ArtSlot'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { tmdbText } from '../i18n/tmdbText'

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
 *
 * 海報位與媒體庫牆共用 `ArtSlot`（票 11）：這裡原本自己寫了一份沒有 `onError` 的 `<img>`，
 * 所以壞掉的 TMDB 海報會露出瀏覽器的破圖示，而媒體庫牆同樣的情況印「無海報」。
 */
export function MediaTile({ item }: { item: DiscoverItem }) {
  const { t, i18n } = useTranslation()
  const title = tmdbText(i18n.language, { 'zh-Hant': item.title, en: item.title_en })
  // 海報也分語言（票 11）：跟標題挑同一輪，中文標題配英文海報是兩個來源拼出來的東西。
  const poster = tmdbText(i18n.language, { 'zh-Hant': item.poster_url, en: item.poster_url_en })

  return (
    <Link
      to="/media/$mediaId"
      params={{ mediaId: item.id }}
      className="grid grid-rows-[auto_1fr] border-2 border-rule bg-well hover:border-rule-strong"
    >
      <ArtSlot url={poster} shape="poster" />
      <div className="grid content-start gap-1 px-3 py-2.5">
        {/* 狀態貼在**這條標識帶**上，不壓在海報上：`deck` 在深色主題是中灰，壓在同樣
            深色的海報上幾乎消失（票 03 實測；DESIGN.md 的 The Paint Needs A Painted
            Ground Rule）。這裡的底是 `well`，量得出對比。
            「部分 / 完整 / 下載中」還沒有——那要等帳本（票 12）才推導得出來。 */}
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="value text-xs text-ink-dim">
            {KIND_CODE[item.kind]} <Dot /> {item.year ?? '—'}
          </span>
          {item.tracked && (
            // 中性色塊：「Berth 為它做過事」是一個事實，不是四個信號色裡的任何一個狀態
            // （The Role Is Not A State Rule）。
            <span className="label bg-deck px-1.5 py-0.5 text-ink">{t('discover.tracked')}</span>
          )}
        </p>
        <p className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">{title}</p>
        {/* 第二行是檔名用的英文標題；EN 介面上它就是第一行，不再印一次。 */}
        {item.title_en !== title && (
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

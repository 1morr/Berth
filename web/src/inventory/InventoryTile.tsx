import { useId } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { InventoryItem, JellyfinWeb } from '../api/inventory'
import { AuditChip } from '../components/AuditChip'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { tmdbText } from '../i18n/tmdbText'
import { jellyfinDetailsUrl } from './jellyfinLink'

/**
 * 六種狀態 → 漆（`.scratch/m1/library-shape.md` §3、The One Meaning Rule）。
 *
 * **常態不塗漆，例外才塗**：一整面牆多半是已入庫的作品，塗成 `secured` 就是一面綠色勾勾牆
 * （DESIGN.md 拒絕的類別預設）。需要人的那幾格才有顏色，所以它們一眼就跳得出來。
 */
const STATUS_SIGNAL = {
  failed: 'blocked',
  review: 'assigned',
  downloading: 'working',
  complete: 'neutral',
  partial: 'neutral',
  empty: 'neutral',
} as const satisfies Record<InventoryItem['status'], Signal>

/**
 * 媒體庫牆上的一格（票 13）。
 *
 * 與探索牆的 `MediaTile` 是同一種貨櫃：海報 + 模板字標識帶、每一格自己的 `border-2`。多出來的是
 * **盤點那一行**（入庫了幾集）與**通往 Jellyfin 的那一條纜繩**。
 *
 * 兩條連結**並排不巢狀**（使用者拍板）：海報與標題那一塊連到 Berth 的 Media 詳情——這一頁的價值
 * 是狀態與修正（brief §12）——Jellyfin 那一行是同一格裡、在它底下的另一條。
 */
export function InventoryTile({ item, web }: { item: InventoryItem; web: JellyfinWeb }) {
  const { t, i18n } = useTranslation()
  const title = tmdbText(i18n.language, { 'zh-Hant': item.title, en: item.title_en })
  const titleId = useId()

  return (
    <article className="grid grid-rows-[1fr_auto] border-2 border-rule bg-well has-[a:hover]:border-rule-strong has-[a:focus-visible]:border-rule-strong">
      <Link
        to="/media/$mediaId"
        params={{ mediaId: item.media_id }}
        className="grid grid-rows-[auto_1fr]"
      >
        <div className="relative aspect-[2/3] bg-hull">
          {item.poster_url ? (
            // 標題就在下面那一行，海報是裝飾性的——給它 alt 只會把同一個名字唸兩次。
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
          {/* 狀態貼在標識帶上，不壓在海報上（The Paint Needs A Painted Ground Rule）。 */}
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="value text-xs text-ink-dim">
              {KIND_CODE[item.kind]} <Dot /> {item.year ?? '—'}
            </span>
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL[STATUS_SIGNAL[item.status]]}`}>
              {t(`inventory.status.${item.status}`)}
            </span>
            <AuditChip count={item.audits} compact />
          </p>
          <h2 id={titleId} className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">
            {title}
          </h2>
          {/* 第二行是檔名用的英文標題；EN 介面上它就是標題本身，不再印一次。 */}
          {item.title_en !== title && (
            <p className="value line-clamp-1 text-xs text-ink-dim">{item.title_en}</p>
          )}
          <p className="value text-xs text-ink">
            {item.kind === 'movie'
              ? item.versions > 0
                ? t('inventory.versions', { count: item.versions })
                : '—'
              : t('inventory.episodes', { imported: item.imported, aired: item.aired })}
          </p>
        </div>
      </Link>
      <JellyfinLine item={item} web={web} titleId={titleId} />
    </article>
  )
}

/**
 * 標識帶最下面那一行：這部作品在 Jellyfin 找到了沒（shape brief §5）。
 *
 * 還沒找到時**說原因，不給一條死連結**（票 13 驗收）。每一格這一行一樣高，基線才對得齊。
 */
function JellyfinLine({
  item,
  web,
  titleId,
}: {
  item: InventoryItem
  web: JellyfinWeb
  titleId: string
}) {
  const { t } = useTranslation()
  const url =
    item.presence === 'found'
      ? jellyfinDetailsUrl(web, item.jellyfin_item_id, window.location)
      : null

  return (
    <div className="flex min-h-10 items-center border-t-2 border-rule px-3 py-1.5 text-xs">
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          // 每一格都有這一條：名字說「開 Jellyfin」，描述說是哪一部（WCAG 2.4.4）。
          aria-describedby={titleId}
          className="label inline-flex min-h-6 items-center text-ink underline decoration-rule-strong decoration-2 underline-offset-4 hover:decoration-ink"
        >
          {t('inventory.jellyfin.open')}
          <span className="sr-only">{t('inventory.jellyfin.newTab')}</span>
        </a>
      ) : item.presence === 'found' ? (
        <span className="text-ink">{t('inventory.jellyfin.noAddress')}</span>
      ) : item.presence === 'searching' ? (
        <span className="text-ink-dim">{t('inventory.jellyfin.searching')}</span>
      ) : item.presence === 'lost' ? (
        <span className="text-ink">{t('inventory.jellyfin.lost')}</span>
      ) : (
        <span className="value text-ink-dim">—</span>
      )}
    </div>
  )
}

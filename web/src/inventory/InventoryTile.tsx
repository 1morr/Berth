import { useId, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { inventoryKey, withWatch, type Inventory, type InventoryCard } from '../api/inventory'
import type { JellyfinWeb } from '../api/jellyfin'
import { ArtSlot } from '../components/ArtSlot'
import { AuditChip } from '../components/AuditChip'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { WatchToggle } from '../components/WatchToggle'
import { watchLine } from '../components/watchLine'
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
} as const satisfies Record<NonNullable<InventoryCard['tracking']>['status'], Signal>

/**
 * 媒體庫牆上的一格（票 13、M1.5 票 03、`.scratch/m1.5/library-shape.md` §5）。
 *
 * 與探索牆的 `MediaTile` 是同一種貨櫃：海報 + 模板字標識帶、每一格自己的 `border-2`。一格有兩種來歷，
 * 版面相同、由資料決定內容：
 *
 * - **Jellyfin 牆上的作品**：Jellyfin 的名稱（不跟 UI 語言）與 Berth 代理的 Jellyfin 海報（票 04），Berth 經手時
 *   疊上狀態與盤點，最下面一定是「在 Jellyfin 開啟」。
 * - **還沒進 Jellyfin 的 Berth 作品**：TMDB 的標題與海報，最下面說它在 Jellyfin 那邊走到哪了。
 *
 * 兩條連結**並排不巢狀**（使用者拍板，票 13）：海報與標題那一塊連到 Berth 的 Media 詳情，Jellyfin 那一行是
 * 同一格裡、在它底下的另一條。沒有 TMDB id 的作品那一塊不是連結，只剩深連結（票 03）。
 *
 * **Jellyfin 那一頁的卡片說得出這個人看到哪了**（票 05）：名稱與盤點行之間一行字，最下面那一行多一顆
 * 「標為已看 / 未看」。`libraryId` 是寫入之後要就地改的那一份快取。
 */
export function InventoryTile({
  card,
  web,
  libraryId,
}: {
  card: InventoryCard
  web: JellyfinWeb
  libraryId: string
}) {
  const { t, i18n } = useTranslation()
  // 在 Jellyfin 裡的作品兩輪是同一個名稱，所以這一步不必分兩種卡片。
  const title = tmdbText(i18n.language, { 'zh-Hant': card.title, en: card.title_en })
  const titleId = useId()
  const tracking = card.tracking

  const body = (
    <>
      <ArtSlot url={card.poster_url} shape="poster" />
      <div className="grid content-start gap-1 px-3 py-2.5">
        {/* 狀態貼在標識帶上，不壓在海報上（The Paint Needs A Painted Ground Rule）。 */}
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="value text-xs text-ink-dim">
            {KIND_CODE[card.kind]} <Dot /> {card.year ?? '—'}
          </span>
          {tracking && (
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL[STATUS_SIGNAL[tracking.status]]}`}>
              {t(`inventory.status.${tracking.status}`)}
            </span>
          )}
          {tracking && <AuditChip count={tracking.audits} compact />}
        </p>
        <h3 id={titleId} className="value line-clamp-2 min-h-10 text-sm leading-snug text-ink">
          {title}
        </h3>
        {/* 還沒進 Jellyfin 的作品，第二行是檔名用的英文標題；EN 介面上它就是標題本身，不再印一次。 */}
        {card.title_en !== title && (
          <p className="value line-clamp-1 text-xs text-ink-dim">{card.title_en}</p>
        )}
        {/* 觀看狀態與盤點行。沒話說時是空的，但留著高度，基線才對得齊。 */}
        <p className="value min-h-4 text-xs text-ink">{card.watch && watchLine(t, card.watch)}</p>
        <p className="value min-h-4 text-xs text-ink">{tracking && <Count card={card} />}</p>
      </div>
    </>
  )

  return (
    <article className="grid grid-rows-[1fr_auto] border-2 border-rule bg-well has-[a:hover]:border-rule-strong has-[a:focus-visible]:border-rule-strong">
      {card.media_id ? (
        <Link
          to="/media/$mediaId"
          params={{ mediaId: card.media_id }}
          className="grid grid-rows-[auto_1fr]"
        >
          {body}
        </Link>
      ) : (
        <div className="grid grid-rows-[auto_1fr]">{body}</div>
      )}
      <JellyfinLine card={card} web={web} titleId={titleId} libraryId={libraryId} />
    </article>
  )
}

function Count({ card }: { card: InventoryCard }): ReactNode {
  const { t } = useTranslation()
  const tracking = card.tracking
  if (!tracking) return null
  if (card.kind === 'movie') {
    return tracking.versions > 0 ? t('inventory.versions', { count: tracking.versions }) : '—'
  }
  return t('inventory.episodes', { imported: tracking.imported, aired: tracking.aired })
}

/**
 * 標識帶最下面那一行：在 Jellyfin 裡就給深連結，還沒進就說原因（票 13 shape §5）。
 *
 * **不給死連結**（票 13 驗收）。每一格這一行一樣高，基線才對得齊；有觀看紀錄的卡片在這一行多一顆
 * 「標為已看 / 未看」（票 05），窄的時候換到下一行。
 */
function JellyfinLine({
  card,
  web,
  titleId,
  libraryId,
}: {
  card: InventoryCard
  web: JellyfinWeb
  titleId: string
  libraryId: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const url =
    card.presence === 'found'
      ? jellyfinDetailsUrl(web, card.jellyfin_item_id, window.location)
      : null

  return (
    <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-t-2 border-rule px-3 py-1.5 text-xs">
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
      ) : card.presence === 'found' ? (
        <span className="text-ink">{t('inventory.jellyfin.noAddress')}</span>
      ) : card.presence === 'searching' ? (
        <span className="text-ink-dim">{t('inventory.jellyfin.searching')}</span>
      ) : card.presence === 'lost' ? (
        <span className="text-ink">{t('inventory.jellyfin.lost')}</span>
      ) : (
        <span className="value text-ink-dim">—</span>
      )}
      {card.watch && (
        <WatchToggle
          itemId={card.jellyfin_item_id}
          target={card.kind === 'tv' ? 'series' : 'movie'}
          watch={card.watch}
          describedBy={titleId}
          // 只改牆上那一格。上方的繼續觀看與下一集（票 07）**不在這裡重問**：它們一換，整面牆就在指標底下
          // 上下移動；它們沒有快取期限，下一次打開頁面或切回視窗時自己會重問。
          onWritten={(written) =>
            queryClient.setQueriesData<Inventory>({ queryKey: inventoryKey(libraryId) }, (data) =>
              data ? withWatch(data, card.jellyfin_item_id, written) : data,
            )
          }
        />
      )}
    </div>
  )
}

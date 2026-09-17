import { useId, type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { InventoryCard, JellyfinWeb } from '../api/inventory'
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
} as const satisfies Record<NonNullable<InventoryCard['tracking']>['status'], Signal>

/**
 * 媒體庫牆上的一格（票 13、M1.5 票 03、`.scratch/m1.5/library-shape.md` §5）。
 *
 * 與探索牆的 `MediaTile` 是同一種貨櫃：海報 + 模板字標識帶、每一格自己的 `border-2`。一格有兩種來歷，
 * 版面相同、由資料決定內容：
 *
 * - **Jellyfin 牆上的作品**：Jellyfin 的名稱（不跟 UI 語言），Berth 經手時疊上狀態與盤點，最下面一定是
 *   「在 Jellyfin 開啟」。海報位是空的——Jellyfin 的圖是票 04。
 * - **還沒進 Jellyfin 的 Berth 作品**：TMDB 的標題與海報，最下面說它在 Jellyfin 那邊走到哪了。
 *
 * 兩條連結**並排不巢狀**（使用者拍板，票 13）：海報與標題那一塊連到 Berth 的 Media 詳情，Jellyfin 那一行是
 * 同一格裡、在它底下的另一條。沒有 TMDB id 的作品那一塊不是連結，只剩深連結（票 03）。
 */
export function InventoryTile({ card, web }: { card: InventoryCard; web: JellyfinWeb }) {
  const { t, i18n } = useTranslation()
  // 在 Jellyfin 裡的作品兩輪是同一個名稱，所以這一步不必分兩種卡片。
  const title = tmdbText(i18n.language, { 'zh-Hant': card.title, en: card.title_en })
  const titleId = useId()
  const tracking = card.tracking

  const body = (
    <>
      <div className="relative aspect-[2/3] bg-hull">
        {card.poster_url ? (
          // 標題就在下面那一行，海報是裝飾性的——給它 alt 只會把同一個名字唸兩次。
          <img
            src={card.poster_url}
            alt=""
            loading="lazy"
            className="size-full object-cover"
            width={342}
            height={513}
          />
        ) : card.presence === 'found' ? null : (
          // 在 Jellyfin 裡的作品有海報，只是還沒接上（票 04），所以不說「沒有海報」。
          <span className="value absolute inset-0 flex items-center justify-center text-xs text-ink-dim">
            {t('discover.noArt')}
          </span>
        )}
      </div>
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
        {/* 盤點行。Berth 沒經手的作品這一行是空的，但留著高度，基線才對得齊（票 05 的觀看狀態排在它上面）。 */}
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
      <JellyfinLine card={card} web={web} titleId={titleId} />
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
 * **不給死連結**（票 13 驗收）。每一格這一行一樣高，基線才對得齊；票 05 的「標為已看」住在這一行。
 */
function JellyfinLine({
  card,
  web,
  titleId,
}: {
  card: InventoryCard
  web: JellyfinWeb
  titleId: string
}) {
  const { t } = useTranslation()
  const url =
    card.presence === 'found'
      ? jellyfinDetailsUrl(web, card.jellyfin_item_id, window.location)
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
      ) : card.presence === 'found' ? (
        <span className="text-ink">{t('inventory.jellyfin.noAddress')}</span>
      ) : card.presence === 'searching' ? (
        <span className="text-ink-dim">{t('inventory.jellyfin.searching')}</span>
      ) : card.presence === 'lost' ? (
        <span className="text-ink">{t('inventory.jellyfin.lost')}</span>
      ) : (
        <span className="value text-ink-dim">—</span>
      )}
    </div>
  )
}

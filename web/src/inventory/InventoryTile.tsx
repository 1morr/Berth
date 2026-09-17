import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import {
  inventoryKey,
  accessRefusal,
  markPlayed,
  withWatch,
  type Inventory,
  type InventoryCard,
  type JellyfinWeb,
  type WatchState,
} from '../api/inventory'
import { AuditChip } from '../components/AuditChip'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { GhostButton, Notice, PrimaryButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { KIND_CODE } from '../components/kind'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
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
      <PosterSlot url={card.poster_url} />
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
        <p className="value min-h-4 text-xs text-ink">
          {card.watch && <Watched watch={card.watch} />}
        </p>
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

/**
 * 2:3 的海報位。網址是空的、或圖載不下來（Jellyfin 回 404、連不上）時同一塊矩形裡印「無海報」，
 * 格子高度不變，牆不壞（票 04）。
 */
function PosterSlot({ url }: { url: string }) {
  const { t } = useTranslation()
  // 記載入失敗的是哪一個網址而不是一個布林值：換頁時同一格換了一張圖，就該重新試。
  const [failed, setFailed] = useState('')

  return (
    <div className="relative aspect-[2/3] bg-hull">
      {url && url !== failed ? (
        // 標題就在下面那一行，海報是裝飾性的——給它 alt 只會把同一個名字唸兩次。
        <img
          src={url}
          alt=""
          loading="lazy"
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

/**
 * 一行只說一件事（判定在後端，`services/watch.py`）：已看、看到幾 %（影片）、剩幾集沒看（劇集，
 * 沒開始看的也說——jellyfin-web 的計數徽章）。都是字，不靠顏色；還沒看過的片什麼都不說。
 */
function Watched({ watch }: { watch: WatchState }): ReactNode {
  const { t } = useTranslation()
  if (watch.played) return t('inventory.watch.played')
  if (watch.progress !== null) return t('inventory.watch.progress', { progress: watch.progress })
  if (watch.unplayed_episodes !== null) {
    return t('inventory.watch.unplayed', { count: watch.unplayed_episodes })
  }
  return null
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
          kind={card.kind}
          watch={card.watch}
          titleId={titleId}
          libraryId={libraryId}
        />
      )}
    </div>
  )
}

/** 比 Ghost 小一號，擠得進卡片最下面那一行（命中面積仍 ≥ 24px）。 */
const TOGGLE =
  'label inline-flex min-h-6 items-center border-2 border-rule px-2 py-1 text-ink hover:border-rule-strong aria-disabled:text-ink-dim'

/**
 * 標為已看 / 未看，寫進這個人在 Jellyfin 的紀錄。**標為未看先就地確認**：觀看次數與最後觀看時間
 * 清掉就找不回來，劇集清的是每一集（研究 §5）。jellyfin-web 兩個方向都不確認；Berth 不提供「復原」，
 * 所以把確認放在送出之前。
 *
 * 寫入之後拿回應改牆上那一格，不重抓整面牆。
 */
function WatchToggle({
  itemId,
  kind,
  watch,
  titleId,
  libraryId,
}: {
  itemId: string
  kind: InventoryCard['kind']
  watch: WatchState
  titleId: string
  libraryId: string
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const router = useRouter()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const warningId = useId()
  const mark = useMutation({
    mutationFn: (played: boolean) => markPlayed(itemId, played),
    onSuccess: (written) =>
      queryClient.setQueriesData<Inventory>({ queryKey: inventoryKey(libraryId) }, (data) =>
        data ? withWatch(data, itemId, written) : data,
      ),
    onError: (error) => {
      // 帳號在 Jellyfin 被停用：後端已經結束 session，重跑守衛把人送回登入頁（與牆那一支同一條路）。
      if (error instanceof ApiError && error.status === 401) void router.invalidate()
    },
  })
  const refusal = accessRefusal(mark.error)

  return (
    <>
      {asked ? (
        <div className="basis-full">
          <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={warningId}>
            <p id={warningId} className="text-xs text-ink">
              {kind === 'tv'
                ? t('inventory.watch.warningSeries')
                : t('inventory.watch.warningMovie')}
            </p>
            {/* 卡片再寬也只有十幾 rem：兩顆鍵永遠疊成一欄。 */}
            <div className="grid gap-2">
              <PrimaryButton
                type="button"
                onClick={() => {
                  close()
                  mark.mutate(false)
                }}
              >
                {t('inventory.watch.markUnplayed')}
              </PrimaryButton>
              <GhostButton type="button" onClick={close}>
                {t('common.cancel')}
              </GhostButton>
            </div>
          </ConfirmPanel>
        </div>
      ) : (
        <button
          ref={trigger}
          type="button"
          aria-describedby={titleId}
          // 送出中不用 `disabled`：確認收起時焦點要回到這一顆，停用的鍵接不住焦點，鍵盤使用者會
          // 掉回 `body`（playwright 實跑抓到）。按鈕照常可按，這一下什麼都不做。
          aria-disabled={mark.isPending || undefined}
          onClick={() => {
            if (mark.isPending) return
            if (watch.played) open()
            else mark.mutate(true)
          }}
          className={TOGGLE}
        >
          {mark.isPending
            ? t('inventory.watch.pending')
            : watch.played
              ? t('inventory.watch.markUnplayed')
              : t('inventory.watch.markPlayed')}
        </button>
      )}
      {/* 失敗就在那一格說原因與下一步，Jellyfin 問不到時貼服務原文（PRODUCT 原則 4）。再按一次就是重試。 */}
      {mark.isError && refusal?.reason !== 'account_disabled' && (
        <div className="grid basis-full gap-1.5">
          <Notice signal="blocked" label={t('common.failed')}>
            {refusal?.reason === 'item_not_visible' || refusal?.reason === 'jellyfin_unreachable'
              ? t(`inventory.watch.refused.${refusal.reason}`)
              : t('inventory.watch.refused.other')}
          </Notice>
          {refusal?.reason === 'jellyfin_unreachable' && refusal.detail && (
            <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
          )}
        </div>
      )}
    </>
  )
}

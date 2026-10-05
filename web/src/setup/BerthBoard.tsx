import type { TFunction } from 'i18next'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { IndexerSetup, RouteSetup, SetupService, TmdbSetup } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { BerthBoard as Board, type BoardSlot } from '../components/BerthBoard'
import { BERTHS, type BerthSlot } from '../components/berths'
import { ORIGIN_LABEL, detailLabel } from '../components/services'
import type { Signal } from '../components/signal'
import { hostOf, signalOf } from './signals'

/**
 * 精靈的泊位板：版面在 `components/BerthBoard.tsx`（健康頁用同一塊），這裡只負責
 * 「一格裡要寫什麼」——使用者選的來源（套件內 / 既有）與測到的實測值（M4 票 15）。
 *
 * 媒體庫路徑與 TMDB 兩格沒有對應的服務——前者的狀態來自 Route 自己的檢查，後者來自
 * TMDB 頁的憑證測試，所以走各自的 `signals`。
 */

/** 每一格各自的信號。三個泊位對到服務，另外兩格對到 Route 與 TMDB 憑證。 */
export type BerthSignals = Partial<Record<BerthSlot, Signal>>

/**
 * 還沒選來源、或沒有對應服務的那兩格用信號本身當標籤。狀態仍然是三重編碼：
 * 色塊 + 這個字 + 泊位號，不看顏色也讀得出來。
 */
const SIGNAL_LABEL = {
  neutral: 'board.unassigned',
  assigned: 'board.waiting',
  working: 'status.running',
  secured: 'status.ok',
  blocked: 'status.failed',
} as const satisfies Record<Signal, string>

/** 產品名不翻譯：詳情列說的是接上的是哪一種軟體。 */
const INDEXER_PRODUCT = { prowlarr: 'Prowlarr', torznab: 'Torznab' } as const

export function BerthBoard({
  services,
  signals = {},
  current,
  indexers,
  tmdb,
  routes,
  reachable,
  onSelect,
}: {
  services: SetupService[]
  /** 那一頁自己的進度覆寫測試結果——連得上不等於那一頁的事做完了。 */
  signals?: BerthSignals
  /** 現在這一頁屬於哪一格（`BERTHS` 的 `code`）。完成頁不屬於任何泊位。 */
  current?: string
  /** 頁 4 起才有：索引站那一格說出接上的是哪一種、加了幾站。 */
  indexers?: IndexerSetup
  /** 頁 5 起才有：TMDB 那一格說出憑證驗過了沒。 */
  tmdb?: TmdbSetup
  /** 頁 3 起才有：媒體庫路徑那一格說出建了幾條 Route（M4 票 31：原本做完了也是「—」）。 */
  routes?: RouteSetup
  /** 點得到哪幾格：走過的與目前的（`setup/navigation.ts` 的 `reachable`）。 */
  reachable?: (slot: BerthSlot) => boolean
  /** 點了哪一格。精靈才給。 */
  onSelect?: (slot: BerthSlot) => void
}) {
  const { t } = useTranslation()
  const byKind = new Map(services.map((row) => [row.kind, row]))

  const slots: BoardSlot[] = BERTHS.map((berth) => {
    const key = berth.slot
    const service = key === 'library' || key === 'tmdb' ? undefined : key
    const chosen = service ? byKind.get(service) : undefined
    const own = signals[key]

    return {
      code: berth.code,
      name: t(berth.nameKey),
      // 狀態字跟著信號（DESIGN 的三重編碼）；來源在詳情列。原本寫來源，紅格與綠格都是「套件內」。
      status: t(SIGNAL_LABEL[own ?? signalOf(chosen)]),
      detail:
        key === 'prowlarr'
          ? withOrigin(t, chosen, indexerDetail(t, chosen, indexers))
          : key === 'tmdb'
            ? tmdbDetail(t, tmdb)
            : key === 'library'
              ? routeDetail(t, routes)
              : withOrigin(t, chosen, serviceDetail(t, service, chosen)),
      signal: own ?? signalOf(chosen),
      filled: Boolean(chosen) || Boolean(own && own !== 'neutral'),
      selectable: reachable?.(key) ?? false,
    }
  })
  const slotOf = new Map<string, BerthSlot>(BERTHS.map((berth) => [berth.code, berth.slot]))

  return (
    <Board
      label={t('board.title')}
      slots={slots}
      current={current}
      summary={{
        expand: t('board.summary.expand'),
        collapse: t('board.summary.collapse'),
        blocked: t('board.summary.blocked'),
      }}
      onSelect={
        onSelect &&
        ((code) => {
          const slot = slotOf.get(code)
          if (slot) onSelect(slot)
        })
      }
    />
  )
}

/** 詳情列前面加上選的來源：「套件內 · 版本 12.1.0」。還沒選就是原本的那一行。 */
function withOrigin(t: TFunction, chosen: SetupService | undefined, detail: ReactNode) {
  if (!chosen) return detail
  const origin = t(ORIGIN_LABEL[chosen.origin])
  if (!detail) return origin
  return (
    <>
      {origin} · {detail}
    </>
  )
}

/** 測到的實測值那一行：版本號，由服務決定（`detailLabel`）。 */
function serviceDetail(
  t: TFunction,
  service: ServiceKind | undefined,
  chosen: SetupService | undefined,
) {
  if (!chosen?.detail || !service) return null
  return (
    <>
      <span className="label">{t(detailLabel(service, chosen.reason))}</span> {chosen.detail}
    </>
  )
}

/**
 * 索引站那一格的詳情列（票 06e）：接上的是哪一種（Prowlarr / Torznab，不寫死），加了幾站。
 *
 * 站數優先讀頁 4 的清單（加完站、或使用者在自己的 Prowlarr 加了站之後，測試時的數字會過期），讀不到
 * 才用測試時的數字。**兩者都沒有就不猜**：還沒測、連不上時測試的詳情是空的，那不是「零站」
 * （票 06e 的 code review）。Torznab 端點沒有站數，說它是哪一台。
 */
function indexerDetail(
  t: TFunction,
  chosen: SetupService | undefined,
  indexers: IndexerSetup | undefined,
) {
  if (!chosen && !indexers) return null
  const kind = indexers?.kind ?? 'prowlarr'
  const product = INDEXER_PRODUCT[kind]
  if (kind === 'torznab') return `${product} · ${hostOf(indexers?.base_url ?? '')}`
  // 頁上的清單讀得到就用它：套件內與既有 Prowlarr 都列了它現在有的站（M4 票 09）。
  const count =
    indexers && indexers.origin !== null && indexers.reachable && !indexers.error
      ? indexers.sites.length
      : chosen?.state === 'ok' && chosen.detail
        ? Number(chosen.detail)
        : null
  if (count === null) return null
  return count > 0
    ? t('board.indexerCount', { product, count })
    : t('board.indexerNone', { product })
}

/** 媒體庫路徑那一格的詳情列：建了幾條 Route。還沒有就留破折號。 */
function routeDetail(t: TFunction, routes: RouteSetup | undefined) {
  const count = routes?.routes.length ?? 0
  return count > 0 ? t('board.routeCount', { count }) : null
}

/**
 * TMDB 那一格的詳情列：憑證驗過了沒。頁 5 之前讀不到，就留破折號。還沒貼過 key 不是「待驗證」
 * ——沒有東西可驗（M4 票 31，與剖面的 `credentialLabel` 同一條）。
 */
function tmdbDetail(t: TFunction, tmdb: TmdbSetup | undefined) {
  if (!tmdb) return null
  const state = !tmdb.api_key_present
    ? 'detail.absent'
    : tmdb.verified
      ? 'detail.verified'
      : 'detail.unverified'
  return (
    <>
      <span className="label">{t('detail.credential')}</span> {t(state)}
    </>
  )
}

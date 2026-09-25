import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { IndexerSetup, ServiceDetection, TmdbSetup } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { BerthBoard as Board, type BoardSlot } from '../components/BerthBoard'
import { BERTHS, type BerthSlot } from '../components/berths'
import { ORIGIN_LABEL, detailLabel } from '../components/services'
import type { Signal } from '../components/signal'
import { signalOf } from './signals'

/**
 * 精靈的泊位板：版面在 `components/BerthBoard.tsx`（健康頁用同一塊），這裡只負責
 * 「一格裡要寫什麼」——判定（套件內 / 既有 / 探測中 / 逾時）與探到的實測值。
 *
 * 媒體庫路徑與 TMDB 兩格沒有對應的服務判定——前者的狀態來自 Route 自己的檢查，後者來自
 * 第 7 步的憑證測試，所以走各自的 `signals`。
 */

/** 每一格各自的信號。三個泊位對到服務，另外兩格對到 Route 與 TMDB 憑證。 */
export type BerthSignals = Partial<Record<BerthSlot, Signal>>

/**
 * 沒有服務判定可顯示的那兩格用信號本身當標籤。狀態仍然是三重編碼：
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
  reachable,
  onSelect,
}: {
  services: ServiceDetection[]
  /** 泊位自己那一步的進度覆寫探測結果——探到了不等於那個泊位的事做完了。 */
  signals?: BerthSignals
  /** 現在這一步屬於哪一格（`BERTHS` 的 `code`）。前置的兩步不屬於任何泊位。 */
  current?: string
  /** 第 6 步起才有：索引站那一格說出接上的是哪一種、加了幾站。 */
  indexers?: IndexerSetup
  /** 第 7 步起才有：TMDB 那一格說出憑證驗過了沒。 */
  tmdb?: TmdbSetup
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
    const detection = service ? byKind.get(service) : undefined
    const own = signals[key]

    return {
      code: berth.code,
      name: t(berth.nameKey),
      status: detection ? t(ORIGIN_LABEL[detection.origin]) : t(SIGNAL_LABEL[own ?? 'neutral']),
      detail:
        key === 'prowlarr'
          ? indexerDetail(t, detection, indexers)
          : key === 'tmdb'
            ? tmdbDetail(t, tmdb)
            : serviceDetail(t, service, detection),
      signal: own ?? signalOf(detection),
      filled: Boolean(detection) || Boolean(own && own !== 'neutral'),
      selectable: reachable?.(key) ?? false,
    }
  })
  const slotOf = new Map<string, BerthSlot>(BERTHS.map((berth) => [berth.code, berth.slot]))

  return (
    <Board
      label={t('board.title')}
      slots={slots}
      current={current}
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

/** 探到的實測值那一行：版本號，由服務決定（`detailLabel`）。 */
function serviceDetail(
  t: TFunction,
  service: ServiceKind | undefined,
  detection: ServiceDetection | undefined,
) {
  if (!detection?.detail || !service) return null
  return (
    <>
      <span className="label">{t(detailLabel(service))}</span> {detection.detail}
    </>
  )
}

/**
 * 索引站那一格的詳情列（票 06e）：接上的是哪一種（Prowlarr / Torznab，不寫死），加了幾站。
 *
 * 套件內探測到、還沒加站時說「尚未加入索引站」，不是一條破折號——判定是「一個索引站都沒有」，
 * 那正是這一格要人去做的事。站數優先讀第 6 步的清單（加完之後判定釘住不再重探，它的數字會過期），
 * 讀不到才用探測時的數字（既有 Prowlarr 報的站數）。**兩者都沒有就不猜**：還在探、沒部署、缺 key 時
 * 判定的詳情是空的，那不是「零站」，說「尚未加入」會把一台有站的 Prowlarr 說錯（票 06e 的 code review）。
 * Torznab 端點沒有站數，說它是哪一台。
 */
function indexerDetail(
  t: TFunction,
  detection: ServiceDetection | undefined,
  indexers: IndexerSetup | undefined,
) {
  if (!detection && !indexers) return null
  const kind = indexers?.kind ?? 'prowlarr'
  const product = INDEXER_PRODUCT[kind]
  if (kind === 'torznab') return `${product} · ${hostOf(indexers?.base_url ?? '')}`
  const count =
    indexers?.origin === 'bundled' && indexers.reachable
      ? indexers.options.filter((row) => row.present).length
      : detection?.detail
        ? Number(detection.detail)
        : detection?.reason === 'no_indexers'
          ? 0
          : null
  if (count === null) return null
  return count > 0
    ? t('board.indexerCount', { product, count })
    : t('board.indexerNone', { product })
}

function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

/** TMDB 那一格的詳情列：憑證驗過了沒。第 7 步之前讀不到，就留破折號。 */
function tmdbDetail(t: TFunction, tmdb: TmdbSetup | undefined) {
  if (!tmdb) return null
  return (
    <>
      <span className="label">{t('detail.credential')}</span>{' '}
      {t(tmdb.verified ? 'detail.verified' : 'detail.unverified')}
    </>
  )
}

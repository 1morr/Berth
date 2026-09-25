import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { ServiceDetection, TmdbSetup } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { BerthBoard as Board, type BoardSlot } from '../components/BerthBoard'
import { BERTHS, SOURCE_SLOT, type BerthSlot } from '../components/berths'
import { ORIGIN_LABEL, detailLabel } from '../components/services'
import type { Signal } from '../components/signal'
import { signalOf } from './signals'

/**
 * 精靈的泊位板：版面在 `components/BerthBoard.tsx`（健康頁用同一塊），這裡只負責
 * 「一格裡要寫什麼」——判定（套件內 / 既有 / 探測中 / 逾時）與探到的實測值。
 *
 * 媒體庫路徑那一格沒有對應的服務判定——它的狀態來自 Route 自己的檢查，所以走
 * `signals.library`。
 */

/** 每一格各自的信號。三個泊位對到服務，媒體庫路徑那一格對到 Route。 */
export type BerthSignals = Partial<Record<ServiceKind | 'library', Signal>>

/**
 * 沒有服務判定可顯示的那一格（媒體庫路徑）用信號本身當標籤。狀態仍然是三重編碼：
 * 色塊 + 這個字 + 泊位號，不看顏色也讀得出來。
 */
const SIGNAL_LABEL = {
  neutral: 'board.unassigned',
  assigned: 'board.waiting',
  working: 'status.running',
  secured: 'status.ok',
  blocked: 'status.failed',
} as const satisfies Record<Signal, string>

export function BerthBoard({
  services,
  signals = {},
  current,
  tmdb,
  reachable,
  onSelect,
}: {
  services: ServiceDetection[]
  /** 泊位自己那一步的進度覆寫探測結果——探到了不等於那個泊位的事做完了。 */
  signals?: BerthSignals
  /** 現在這一步屬於哪一格（`BERTHS` 的 `code`）。前置的兩步不屬於任何泊位。 */
  current?: string
  /**
   * 「來源」那一格的另一半。走到第 7 步之後才有值——在那之前這一格說的是索引站，
   * 之後說的是閘門（見 `sourceDetail`）。
   */
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
    const service = key === 'library' ? undefined : key
    const detection = service ? byKind.get(service) : undefined
    const own = signals[key]

    return {
      code: berth.code,
      name: t(berth.nameKey),
      status: detection ? t(ORIGIN_LABEL[detection.origin]) : t(SIGNAL_LABEL[own ?? 'neutral']),
      detail:
        key === SOURCE_SLOT && tmdb ? sourceDetail(t, tmdb) : serviceDetail(t, service, detection),
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

/** 探到的實測值那一行：版本號或索引站數量，由服務決定（`detailLabel`）。 */
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
 * 「來源」那一格走到 TMDB 那一半之後的詳情列（票 03 第 4 條）。
 *
 * 這一格是「來源」，它有兩半：索引站與 TMDB。索引站那一半連不上幾站是常態、不擋路，
 * TMDB 是**必填的閘門**（plan §9.3 第 7 步）——所以一旦拿得到 TMDB 的判定，這一格
 * 要說的就是閘門過了沒，而不是繼續停在索引站數。這一行只容得下一個短語（版面是
 * 一列 truncate），兩件事並列會把後面那件截掉，所以是換不是接。
 */
function sourceDetail(t: TFunction, tmdb: TmdbSetup) {
  return (
    <>
      <span className="label">{t('detail.tmdb')}</span>{' '}
      {t(tmdb.verified ? 'detail.verified' : 'detail.unverified')}
    </>
  )
}

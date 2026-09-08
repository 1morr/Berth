import { useTranslation } from 'react-i18next'

import type { ServiceDetection } from '../api/setup'
import type { ServiceKind } from '../api/schemas'
import { BerthBoard as Board, type BoardSlot } from '../components/BerthBoard'
import { BERTHS } from '../components/berths'
import { ORIGIN_LABEL, detailLabel } from '../components/services'
import type { Signal } from '../components/signal'
import { signalOf } from './signals'

/**
 * 精靈的泊位板：版面在 `components/BerthBoard.tsx`（健康頁用同一塊），這裡只負責
 * 「一格裡要寫什麼」——判定（套件內 / 既有 / 探測中 / 逾時）與探到的實測值。
 *
 * 泊位 4（媒體庫路徑）沒有對應的服務判定——它的狀態來自 Route 自己的檢查，所以走
 * `signals.library`。
 */

/** 四格各自的信號。三個泊位對到服務，第四個（媒體庫路徑）對到 Route。 */
export type BerthSignals = Partial<Record<ServiceKind | 'library', Signal>>

/**
 * 沒有服務判定可顯示的那一格（泊位 4）用信號本身當標籤。狀態仍然是三重編碼：
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
}: {
  services: ServiceDetection[]
  /** 泊位自己那一步的進度覆寫探測結果——探到了不等於那個泊位的事做完了。 */
  signals?: BerthSignals
  /** 現在這一步屬於哪一格（`BERTHS` 的 `code`）。前置的兩步不屬於任何泊位。 */
  current?: string
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
        detection?.detail && service ? (
          <>
            <span className="label">{t(detailLabel(service))}</span> {detection.detail}
          </>
        ) : null,
      signal: own ?? signalOf(detection),
      filled: Boolean(detection) || Boolean(own && own !== 'neutral'),
    }
  })

  return <Board label={t('board.title')} slots={slots} current={current} />
}

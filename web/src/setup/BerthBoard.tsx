import { useTranslation } from 'react-i18next'

import type { ServiceDetection, ServiceKind } from '../api/setup'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { ORIGIN_LABEL, detailLabel, signalOf } from './signals'

/**
 * 常駐的泊位板橫幅：四格等寬塗裝色塊。狀態三重編碼——色塊 + 模板字標籤 + 泊位號，
 * 不看顏色也讀得出來（direction contract）。格子裡的每個字都是資訊：泊位碼、服務名、
 * 判定（套件內 / 既有 / 探測中 / 逾時）、實測值。
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

/**
 * `code` 是泊位識別碼，不是文案，所以不走 i18n——ISO 6346 的貨櫃標識、船期表的泊位號
 * 在哪個語言都是同一串字母數字。會翻譯的是 `nameKey`。
 */
interface BerthSlot {
  code: string
  nameKey: 'board.jellyfin' | 'board.qbittorrent' | 'board.source' | 'board.library'
  /** 這一格在 `signals` 裡的鍵；前三個同時也是它探測的服務。 */
  key: ServiceKind | 'library'
  service?: ServiceKind
}

const SLOTS: readonly BerthSlot[] = [
  { code: 'BTH 1', nameKey: 'board.jellyfin', key: 'jellyfin', service: 'jellyfin' },
  { code: 'BTH 2', nameKey: 'board.qbittorrent', key: 'qbittorrent', service: 'qbittorrent' },
  { code: 'BTH 3', nameKey: 'board.source', key: 'prowlarr', service: 'prowlarr' },
  { code: 'BTH 4', nameKey: 'board.library', key: 'library' },
]

export function BerthBoard({
  services,
  signals = {},
}: {
  services: ServiceDetection[]
  /** 泊位自己那一步的進度覆寫探測結果——探到了不等於那個泊位的事做完了。 */
  signals?: BerthSignals
}) {
  const { t } = useTranslation()
  const byKind = new Map(services.map((row) => [row.kind, row]))

  return (
    <section aria-label={t('board.title')} className="border-b-2 border-rule-strong bg-hull">
      {/* 手機收成水平捲動的四格；桌機一列四格等寬（direction contract）。 */}
      <ul className="flex snap-x gap-px overflow-x-auto bg-rule-strong sm:grid sm:grid-cols-4 sm:overflow-visible">
        {SLOTS.map((slot) => {
          const detection = slot.service ? byKind.get(slot.service) : undefined
          const own = signals[slot.key]
          const signal = own ?? signalOf(detection)

          return (
            <li
              key={slot.code}
              className={`min-w-52 flex-1 snap-start px-4 py-3 ${
                detection || (own && own !== 'neutral')
                  ? SIGNAL_FILL[signal]
                  : 'bg-well text-ink-dim'
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="value text-xs font-semibold">{slot.code}</span>
                <span className="label opacity-80">
                  {detection
                    ? t(ORIGIN_LABEL[detection.origin])
                    : t(SIGNAL_LABEL[own ?? 'neutral'])}
                </span>
              </div>
              <p className="value mt-2 truncate text-base font-semibold">{t(slot.nameKey)}</p>
              <p className="value mt-1 h-4 truncate text-xs opacity-80">
                {detection?.detail && slot.service ? (
                  <>
                    <span className="label opacity-70">{t(detailLabel(slot.service))}</span>{' '}
                    {detection.detail}
                  </>
                ) : (
                  '—'
                )}
              </p>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

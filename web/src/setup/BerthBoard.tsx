import { useTranslation } from 'react-i18next'

import type { ServiceDetection, ServiceKind } from '../api/setup'
import { SIGNAL_FILL, type Signal } from '../components/signal'
import { ORIGIN_LABEL, detailLabel, signalOf } from './signals'

/**
 * 常駐的泊位板橫幅：四格等寬塗裝色塊。狀態三重編碼——色塊 + 模板字標籤 + 泊位號，
 * 不看顏色也讀得出來（direction contract）。格子裡的每個字都是資訊：泊位碼、服務名、
 * 判定（套件內 / 既有 / 探測中 / 逾時）、實測值。
 *
 * 泊位 4 在票 05 永遠是未指派：它要等媒體庫路徑那一步（票 09）。
 */

/**
 * `code` 是泊位識別碼，不是文案，所以不走 i18n——ISO 6346 的貨櫃標識、船期表的泊位號
 * 在哪個語言都是同一串字母數字。會翻譯的是 `nameKey`。
 */
interface BerthSlot {
  code: string
  nameKey: 'board.jellyfin' | 'board.qbittorrent' | 'board.source' | 'board.library'
  service?: ServiceKind
}

const SLOTS: readonly BerthSlot[] = [
  { code: 'BTH 1', nameKey: 'board.jellyfin', service: 'jellyfin' },
  { code: 'BTH 2', nameKey: 'board.qbittorrent', service: 'qbittorrent' },
  { code: 'BTH 3', nameKey: 'board.source', service: 'prowlarr' },
  { code: 'BTH 4', nameKey: 'board.library' },
]

export function BerthBoard({
  services,
  signals = {},
}: {
  services: ServiceDetection[]
  /** 泊位自己那一步的進度覆寫探測結果——探到了不等於那個泊位的事做完了。 */
  signals?: Partial<Record<ServiceKind, Signal>>
}) {
  const { t } = useTranslation()
  const byKind = new Map(services.map((row) => [row.kind, row]))

  return (
    <section aria-label={t('board.title')} className="border-b-2 border-rule-strong bg-hull">
      {/* 手機收成水平捲動的四格；桌機一列四格等寬（direction contract）。 */}
      <ul className="flex snap-x gap-px overflow-x-auto bg-rule-strong sm:grid sm:grid-cols-4 sm:overflow-visible">
        {SLOTS.map((slot) => {
          const detection = slot.service ? byKind.get(slot.service) : undefined
          const signal = (slot.service && signals[slot.service]) ?? signalOf(detection)

          return (
            <li
              key={slot.code}
              className={`min-w-52 flex-1 snap-start px-4 py-3 ${
                detection || (slot.service && signals[slot.service])
                  ? SIGNAL_FILL[signal]
                  : 'bg-well text-ink-dim'
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="value text-xs font-semibold">{slot.code}</span>
                <span className="label opacity-80">
                  {detection ? t(ORIGIN_LABEL[detection.origin]) : t('board.unassigned')}
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

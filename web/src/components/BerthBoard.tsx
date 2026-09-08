import type { ReactNode } from 'react'

import { SIGNAL_FILL, type Signal } from './signal'

/**
 * 泊位板橫幅：四格等寬塗裝色塊（direction contract 的 FIRST VIEWPORT）。
 *
 * 狀態三重編碼——色塊 + 模板字標籤 + 泊位號，不看顏色也讀得出來。格子裡的每個字都是資訊。
 *
 * **精靈與健康頁是同一塊板**：那四個泊位（Jellyfin / qBittorrent / 來源 / 媒體庫路徑）
 * 是同一組東西，精靈問「接上了沒」，健康頁問「還繫著嗎」。所以這裡只有版面，一格裡要
 * 寫什麼由呼叫端決定。
 */

export interface BoardSlot {
  /** 泊位識別碼（`BERTHS` 的 `code`）。 */
  code: string
  /** 已經翻譯好的服務名。 */
  name: string
  /** 已經翻譯好的狀態標籤（判定或信號）。 */
  status: string
  /** 實測值那一行。沒有值時留一條破折號，四格的高度才不會跳。 */
  detail?: ReactNode
  signal: Signal
  /** 塗上色塊，還是留在中性底色上（還沒有任何結果的格子）。 */
  filled?: boolean
}

export function BerthBoard({ label, slots }: { label: string; slots: readonly BoardSlot[] }) {
  return (
    <section aria-label={label} className="border-b-2 border-rule-strong bg-hull">
      {/* 手機收成水平捲動的四格；桌機一列四格等寬（direction contract）。
          欄數寫死成四：泊位就是那四個（Jellyfin / qBittorrent / 來源 / 媒體庫路徑），
          而且 Tailwind 看不見組出來的類名。 */}
      <ul className="flex snap-x gap-px overflow-x-auto bg-rule-strong sm:grid sm:grid-cols-4 sm:overflow-visible">
        {slots.map((slot) => (
          <li
            key={slot.code}
            className={`min-w-52 flex-1 snap-start px-4 py-3 ${
              slot.filled === false ? 'bg-well text-ink-dim' : SIGNAL_FILL[slot.signal]
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="value text-xs font-semibold">{slot.code}</span>
              <span className="label opacity-80">{slot.status}</span>
            </div>
            <p className="value mt-2 truncate text-base font-semibold">{slot.name}</p>
            <p className="value mt-1 h-4 truncate text-xs opacity-80">{slot.detail || '—'}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

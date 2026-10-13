import { Fragment, type ReactNode } from 'react'

import { FILTER_ACTIVE } from './controls'

/**
 * 一頁裡的一組單選篩選（媒體庫的待審 / 對不到、下載列表、作品頁的下載段；M4 票 92 收成這一份）。
 *
 * **選著的那一個不是連結**，是一段 `aria-current="true"` 的字（M1.5 票 13，DESIGN.md Navigation）：`Link`
 * 當前時一定掛 `aria-current="page"`，而同一頁的切換列已經有一個「當前頁」。其餘的由呼叫端畫（`renderOption`）
 * ——路由的 `Link` 或按鈕各有各的去處，外觀是 `FILTER`。可多選的切換鍵是另一種（`ToggleChips`）。
 */
export function FilterBar<V extends string | undefined>({
  label,
  options,
  current,
  renderOption,
  className = '',
}: {
  /** 整組的名字（`<nav aria-label>`）。 */
  label: string
  /**
   * 照這裡的先後排。`value` 是 React 的 key（一組裡不重複，`undefined` 是「全部」那一種）：`label` 帶著即時的件數，
   * 拿它當 key 的話件數一變那一顆就重建，鍵盤停在上面的焦點跟著掉（code-review）。
   */
  options: readonly { value: V; label: string }[]
  current: V
  renderOption: (value: V, label: string) => ReactNode
  className?: string
}) {
  return (
    <nav aria-label={label} className={`flex flex-wrap gap-2 ${className}`}>
      {options.map((entry) =>
        entry.value === current ? (
          <span key={entry.value ?? ''} aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>
            {entry.label}
          </span>
        ) : (
          <Fragment key={entry.value ?? ''}>{renderOption(entry.value, entry.label)}</Fragment>
        ),
      )}
    </nav>
  )
}

import { useId } from 'react'

import { FILTER, FILTER_ACTIVE } from './controls'

/** 一顆切換鍵：值、看得見的字，與可選的筆數（篩選按鈕上的那個數字）或標記。 */
export interface ToggleChip<T extends string> {
  value: T
  label: string
  count?: number
  /** 標籤是機器字串（會送出去的名字）：走 `.value` 原樣，不被 `.label` 大寫（The Machine String Rule）。 */
  machine?: boolean
  /** 跟在標籤後面的小字（名字 chip 的「英文名」「原名」，票 84）。算進可存取名稱。 */
  note?: string
}

/**
 * 一組可多選的切換鍵（M4 票 83 的搜尋結果篩選；票 84 的名字與季選擇用同一個）。
 *
 * 外觀是篩選列那一種方塊（`FILTER` / `FILTER_ACTIVE`，DESIGN.md〈Navigation〉）：按下的那幾顆是重線加 `deck` 底，
 * 不靠顏色。每一顆是 `aria-pressed` 的按鈕，整組是一個 `role="group"`，名稱由 `label` 給（畫面上不另外印）。
 * 筆數走 `.value`，與標籤之間有一個空白——不然可存取名稱會黏成「符合13」；標記同理。
 *
 * 選了哪幾顆由呼叫端記（`selected`）：這裡只畫、只回報按了哪一顆，切換用 `toggled.ts` 的 `toggled`。
 */
export function ToggleChips<T extends string>({
  label,
  chips,
  selected,
  onToggle,
}: {
  label: string
  chips: readonly ToggleChip<T>[]
  selected: ReadonlySet<T>
  onToggle: (value: T) => void
}) {
  const labelId = useId()

  return (
    <div role="group" aria-labelledby={labelId} className="flex flex-wrap gap-2">
      <span id={labelId} className="sr-only">
        {label}
      </span>
      {chips.map((chip) => {
        const pressed = selected.has(chip.value)
        return (
          <button
            key={chip.value}
            type="button"
            aria-pressed={pressed}
            onClick={() => onToggle(chip.value)}
            className={`${pressed ? `${FILTER_ACTIVE} text-ink` : FILTER} max-w-full flex-wrap gap-x-2 gap-y-1 text-start disabled:cursor-not-allowed disabled:text-ink-dim`}
          >
            {chip.machine ? (
              <span className="value text-sm tracking-normal wrap-anywhere normal-case">
                {chip.label}
              </span>
            ) : (
              chip.label
            )}
            {chip.note !== undefined && (
              <>
                {' '}
                <span className="text-ink-dim">{chip.note}</span>
              </>
            )}
            {chip.count !== undefined && (
              <>
                {' '}
                <span className="value text-xs">{chip.count}</span>
              </>
            )}
          </button>
        )
      })}
    </div>
  )
}

import type { ReactNode } from 'react'

/**
 * 區塊標題：`.label` 模板字壓在一條重橫線上，旁邊一個 `.value` 的計數（DESIGN.md Typography 的
 * 「頁面與區塊的標題不另立一階大字」）。`extra` 是標題列上的第二個訊號（待綁定那一塊漆）。
 *
 * 只有數字的計數：看得見的是數字（`aria-hidden`），聽得見的是帶單位的那一句（DESIGN.md 區塊標題）。
 */
export function SectionHeading({
  id,
  label,
  count,
  extra,
}: {
  id: string
  label: string
  /** 看得見的數字與帶單位的那一句（「12 筆」）。標題列上已經有一塊漆說出數量的（待綁定）不給。 */
  count?: { value: number; spoken: string }
  extra?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
      <h2 id={id} className="label text-ink">
        {label}
      </h2>
      {count && (
        <>
          <span aria-hidden="true" className="value text-xs text-ink-dim">
            {count.value}
          </span>
          <span className="sr-only">{count.spoken}</span>
        </>
      )}
      {extra}
    </div>
  )
}

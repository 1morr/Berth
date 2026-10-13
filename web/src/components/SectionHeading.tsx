import type { ReactNode, Ref } from 'react'

/**
 * 區塊標題：`.label` 模板字壓在一條重橫線上，旁邊一個 `.value` 的計數（DESIGN.md Typography 的
 * 「頁面與區塊的標題不另立一階大字」）。頁內每個區塊都用這一個（M4 票 92）；頁級的 `h1` 不是它。
 *
 * 只有數字的計數：看得見的是數字（`aria-hidden`），聽得見的是帶單位的那一句（DESIGN.md 區塊標題）。
 * 計數本身就是一整句的（「共 12 筆結果」「剩 3 集沒看」）、標題列上的一塊漆、靠右的連結與篩選列走 `extra`；
 * 要靠右的自己帶 `ms-auto`。
 */
export function SectionHeading({
  id,
  label,
  count,
  extra,
  headingRef,
}: {
  id: string
  label: string
  /** 看得見的數字與帶單位的那一句（「12 筆」）。標題列上已經有一塊漆說出數量的（待綁定）不給。 */
  count?: { value: number; spoken: string }
  extra?: ReactNode
  /**
   * 程式要把焦點送進標題時給（搜尋段：季表那兩顆按鈕按下之後）。給了就 `tabIndex={-1}`：送得進，
   * 但不進 Tab 順序。
   */
  headingRef?: Ref<HTMLHeadingElement>
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
      <h2
        id={id}
        ref={headingRef}
        tabIndex={headingRef ? -1 : undefined}
        className="label text-ink"
      >
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

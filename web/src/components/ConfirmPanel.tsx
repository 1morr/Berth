import type { KeyboardEvent, ReactNode, Ref } from 'react'

/**
 * 就地確認的外殼：一個有名字的 group，焦點進得來、Esc 收得起（DESIGN.md 的 The Focus Follows
 * The Confirm Rule）。名字指向說明後果的那一句，所以焦點落進來時螢幕閱讀器先念後果。
 *
 * `panelRef` 與 `onKeyDown` 來自 `useInPlaceConfirm`。
 */
export function ConfirmPanel({
  panelRef,
  onKeyDown,
  labelledBy,
  children,
}: {
  panelRef: Ref<HTMLDivElement>
  onKeyDown: (event: KeyboardEvent) => void
  /** 說明按下去會發生什麼的那一句的 `id`。 */
  labelledBy: string
  children: ReactNode
}) {
  return (
    <div
      ref={panelRef}
      role="group"
      aria-labelledby={labelledBy}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      className="grid gap-3 border-2 border-rule-strong bg-well px-3 py-3"
    >
      {children}
    </div>
  )
}

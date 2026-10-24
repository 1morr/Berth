import { useEffect, useRef } from 'react'

/**
 * 就地動作做完、按下去的那一顆跟著消失時（確認卡的確認與拒絕、撤銷），焦點交給說結果的那一格
 * （The Focus Follows The Confirm Rule 的成功那條路）。`settled` 從 `false` 變成 `true` 的那一刻給一次；
 * 一開始就是 `true` 的（重整之後畫出來的舊卡）不給。
 *
 * 只在焦點**真的掉了**（落在 `body`）時動手，同 `useFocusAfterRemoval`：別處觸發的同一件事（AI 活動頁撤銷了
 * 面板裡那張卡）、使用者已經在輸入框打字，都不會被搶走。回傳的 ref 掛在那一格上，它要 `tabIndex={-1}`。
 */
export function useFocusOnSettle<T extends HTMLElement>(settled: boolean) {
  const target = useRef<T>(null)
  const was = useRef(settled)
  useEffect(() => {
    const arrived = settled && !was.current
    was.current = settled
    if (!arrived) return
    const active = document.activeElement
    if (active !== null && active !== document.body) return
    target.current?.focus()
  }, [settled])
  return target
}

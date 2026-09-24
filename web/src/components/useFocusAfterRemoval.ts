import { useCallback } from 'react'

/**
 * 工作清單上按完的那一列會消失，而按下去的那一顆跟著它一起走——焦點掉回 `body`，鍵盤使用者清
 * 一件就要從頁首重新 Tab 一次（M2 票 16 的 critique）。`useInPlaceConfirm` 只管得到「取消」那條路：
 * 它把焦點還給觸發鍵，而成功之後觸發鍵已經不在了。
 *
 * 回傳的 ref 掛在**不會跟著清單一起消失**的那一層：焦點在某一列（`<article>`）裡時記下它是第幾列；
 * **那一列被拿掉**、焦點落到 `body` 時，改落在接替那個位置的那一列。一列都不剩時落在那一層裡的
 * `<h1>`，沒有 `<h1>` 就落在那一層自己（兩者都要 `tabIndex={-1}`）。只在焦點**真的掉了**時動手：
 * 使用者自己點到別處、或確認區收起時把焦點還給觸發鍵（那是同步的，早於這裡），都不會被搶走。
 *
 * callback ref 而不是 `useRef` + effect：媒體庫的子集清單先畫讀取中、資料回來才有那一層。
 */
export function useFocusAfterRemoval() {
  return useCallback((root: HTMLElement | null) => {
    if (!root) return
    // 焦點最後待過的那一列與它當時的位置。**那一列還在就不動**（M2 票 16 的 audit）：使用者自己點到
    // 空白處時焦點也在 `body`，那時對帳進度、重問回來的清單之類的變動不該把他拉回去。
    let last: { row: Element; index: number } | null = null

    const onFocusIn = (event: FocusEvent) => {
      const row = event.target instanceof Element ? event.target.closest('article') : null
      last = row ? { row, index: [...root.querySelectorAll('article')].indexOf(row) } : null
    }
    const observer = new MutationObserver(() => {
      if (last === null || last.row.isConnected) return
      const active = document.activeElement
      if (active !== null && active !== document.body) return
      const rows = root.querySelectorAll<HTMLElement>('article')
      const next = rows[Math.min(last.index, rows.length - 1)] ?? root.querySelector('h1') ?? root
      next.focus()
    })

    root.addEventListener('focusin', onFocusIn)
    observer.observe(root, { childList: true, subtree: true })
    return () => {
      root.removeEventListener('focusin', onFocusIn)
      observer.disconnect()
    }
  }, [])
}

import { useCallback, useState } from 'react'

/** 面板開著沒有，記在這台瀏覽器（shape 第 6 節：換頁不關、重整照原樣）。 */
const KEY = 'berth.assistant.open'

/** 面板並排的寬度（Tailwind 的 `lg`）：以下面板取代頁面。 */
const WIDE = '(min-width: 64rem)'

/** 面板與頁面並排得下嗎。沒有 `matchMedia` 的環境（jsdom）當桌機。 */
export function isWide(): boolean {
  return typeof window.matchMedia !== 'function' || window.matchMedia(WIDE).matches
}

/**
 * 讀不到（私密視窗、被擋的 site data）就當關著；寫不進去也照樣開關，只是重整不記得。
 *
 * **只有並排得下時照記憶打開**（M5 票 15）：`lg` 以下面板取代頁面，照記憶打開等於每次從通知點進來、
 * 先看到的是上次沒關的助理而不是那一頁。
 */
export function usePanelOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1' && isWide()
    } catch {
      return false
    }
  })
  const change = useCallback((next: boolean) => {
    setOpen(next)
    try {
      localStorage.setItem(KEY, next ? '1' : '0')
    } catch {
      // 記不住就算了：這只是方便，不是狀態。
    }
  }, [])
  return [open, change]
}

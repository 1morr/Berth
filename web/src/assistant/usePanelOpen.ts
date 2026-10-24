import { useCallback, useState } from 'react'

/** 面板開著沒有，記在這台瀏覽器（shape 第 6 節：換頁不關、重整照原樣）。 */
const KEY = 'berth.assistant.open'

/**
 * 讀不到（私密視窗、被擋的 site data）就當關著；寫不進去也照樣開關，只是重整不記得。
 */
export function usePanelOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1'
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

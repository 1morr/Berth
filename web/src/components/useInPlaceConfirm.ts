import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

/**
 * 就地展開的二次確認（The Failure Expands In Place Rule）的焦點與鍵盤。
 *
 * 確認不是 dialog，所以瀏覽器不會替它管焦點：展開時焦點要進到確認裡（螢幕閱讀器才念得到
 * 那段後果說明），取消或 Esc 收起時要回到觸發鍵。沒有這兩步的話焦點掉回 `body`，鍵盤使用者
 * 得從頁首重新 Tab 一遍才回得到原處（票 15 的 critique 實測）。
 *
 * 確認區塊掛 `panel`、`tabIndex={-1}` 與 `onKeyDown`；觸發鍵掛 `trigger`。
 */
export function useInPlaceConfirm() {
  const [asked, setAsked] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  // 只有「收起」才把焦點送回觸發鍵：第一次畫出來時觸發鍵也是 `asked === false`，
  // 那時搶焦點會把使用者從他正在看的地方拉走。
  const returning = useRef(false)

  useEffect(() => {
    if (asked) {
      panel.current?.focus()
    } else if (returning.current) {
      returning.current = false
      trigger.current?.focus()
    }
  }, [asked])

  const close = () => {
    returning.current = true
    setAsked(false)
  }

  return {
    asked,
    open: () => setAsked(true),
    close,
    trigger,
    panel,
    onKeyDown: (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      // 確認可能在另一個會吃 Esc 的東西裡（`<details>`）；這一下只收起確認。
      event.stopPropagation()
      close()
    },
  }
}

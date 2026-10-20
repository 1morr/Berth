import { useEffect, useRef, type ReactNode } from 'react'

/**
 * 精靈每一步的版面：工作面與剖面（`.scratch/m0/wizard-shape.md` §6）。
 *
 * **DOM 裡工作面在前**（票 06h 的 critique 與 audit）：窄版第一屏是這一步的標題與動作，剖面
 * 接在後面——原本剖面在前，390 寬時標題要捲到 800–1500px 才出現；標題順序也因此是 h2（這一步）
 * → h3（剖面），不再是 h1 直接跳 h3。桌機用 grid 把剖面放回左欄，看起來與原本一樣。剖面只放
 * 讀的東西：要填要按的（例如套件內 Jellyfin 的媒體庫清單）放工作面，Tab 順序才與視覺一致。
 *
 * **焦點不掉回 `body`**（同一輪 audit，WCAG 2.4.3）：換步時舊的一頁整個卸下、按下的動作做完
 * 那顆鍵被換掉，焦點都會掉到 `body`，鍵盤的人得從頁首重新 Tab。這一步掛上時焦點給它的 h2；
 * 之後**最後有焦點的那個元素被拿掉了**、焦點在 `body` 時，接回「前往下一個泊位」（做完了才有），
 * 沒有就接回 h2。只看「被拿掉」，與 `useFocusAfterRemoval` 同一條規則、同一種做法
 * （MutationObserver）：使用者自己點到空白處時焦點也在 `body`，那時不動他；換鍵只發生在這一步
 * 自己的 state 裡、StepFrame 沒有重繪時也接得回來（code review 抓到原本靠重繪檢查接不到）。
 * 清單逐列移除時 `useFocusAfterRemoval` 的 observer 先建立、先跑，它把焦點給了下一列，這裡就不動。
 */
export function StepFrame({ cutaway, children }: { cutaway: ReactNode; children: ReactNode }) {
  const work = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const frame = work.current
    if (!frame) return
    let last: Element | null = null
    const remember = (event: FocusEvent) => {
      last = event.target instanceof Element ? event.target : null
    }
    const observer = new MutationObserver(() => {
      const active = document.activeElement
      if (last === null || last.isConnected || (active !== null && active !== document.body)) return
      const next = frame.querySelector<HTMLElement>('[data-berth-next]')
      if (next) next.focus({ preventScroll: true })
      else focusHeading(frame, { preventScroll: true })
    })

    frame.addEventListener('focusin', remember)
    observer.observe(frame, { childList: true, subtree: true })
    // 這一步自己把焦點放到某個欄位上了（`autoFocus`），不搶。
    if (!frame.contains(document.activeElement)) focusHeading(frame, { preventScroll: false })
    return () => {
      frame.removeEventListener('focusin', remember)
      observer.disconnect()
    }
  }, [])

  return (
    <div className="grid flex-1 gap-px bg-rule lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div ref={work} className="min-w-0 bg-hull p-6 lg:col-start-2 lg:row-start-1">
        {children}
      </div>
      <div className="min-w-0 bg-hull p-6 lg:col-start-1 lg:row-start-1">
        <div className="lg:sticky lg:top-6">{cutaway}</div>
      </div>
    </div>
  )
}

function focusHeading(frame: HTMLElement, options: FocusOptions) {
  const heading = frame.querySelector<HTMLElement>('h2')
  if (!heading) return
  // 標題本來不在 Tab 順序裡，也不該進去：-1 只讓程式把焦點放上來。
  heading.tabIndex = -1
  heading.focus(options)
}

import { useSyncExternalStore } from 'react'

/** Tailwind 的 `lg`：`StepFrame` 從這個寬度起排成兩欄。 */
const WIDE = '(min-width: 64rem)'

function query(): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(WIDE) : null
}

function subscribe(onChange: () => void) {
  const list = query()
  list?.addEventListener('change', onChange)
  return () => list?.removeEventListener('change', onChange)
}

/**
 * 畫面寬到 `StepFrame` 排成兩欄了沒（M4 票 119）。同一塊東西在桌機與窄版要排在 DOM 的不同位置時用它：
 * CSS 搬得動位置、搬不動 Tab 順序。量不到（沒有 `matchMedia`）當窄版，單欄的順序在哪裡都讀得通。
 */
export function useWideScreen(): boolean {
  return useSyncExternalStore(subscribe, () => query()?.matches ?? false)
}

import { useSyncExternalStore } from 'react'

/** Tailwind 的 `lg`（64rem）以下：面板蓋滿整個視窗、底下那一頁 `inert`。 */
const NARROW = '(max-width: 63.999rem)'

function query(): MediaQueryList | null {
  // jsdom 沒有 `matchMedia`：測試裡當成桌面。
  return typeof window.matchMedia === 'function' ? window.matchMedia(NARROW) : null
}

function subscribe(onChange: () => void) {
  const list = query()
  list?.addEventListener('change', onChange)
  return () => list?.removeEventListener('change', onChange)
}

export function useNarrow(): boolean {
  return useSyncExternalStore(subscribe, () => query()?.matches ?? false)
}

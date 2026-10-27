import { useSyncExternalStore } from 'react'

import { usePanel } from './panelState'

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

/**
 * 從面板連到別頁時的 `onClick`：窄版的面板蓋滿整個視窗，不收起來的話換過去的那一頁看不到。
 * 桌面上面板與頁面並排，留著。
 */
export function useLeavePanel(): () => void {
  const narrow = useNarrow()
  const { setOpen } = usePanel()
  return () => {
    if (narrow) setOpen(false)
  }
}

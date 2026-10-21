import { useEffect, useRef } from 'react'
import { useLocation } from '@tanstack/react-router'

/**
 * 通知裡的連結帶著 `#plan-12`、`#issue-5` 這種片段，指名清單上的哪一列（M4 票 127）。清單是資料
 * 回來才畫的，瀏覽器原生的錨點捲動早已錯過，所以由這裡在 `ready` 之後補上：捲到畫面中央、焦點落
 * 在那一列。
 *
 * **每個片段值只做一次**：之後重問資料、重畫都不再動，否則使用者自己捲走或點到別處會被拉回來。
 * 找不到那一列（已經有人處理掉了）就什麼都不做。目標藏在收著的 `<details>` 裡（一組 audit 的成員）時
 * 先把外層攤開，否則捲不到也聚焦不了。
 */
export function useHashTarget(ready: boolean) {
  const hash = useLocation({ select: (location) => location.hash })
  const handled = useRef('')

  useEffect(() => {
    if (!ready || hash === '' || handled.current === hash) return
    handled.current = hash
    const target = document.getElementById(hash)
    if (target === null) return
    for (let at = target.parentElement; at !== null; at = at.parentElement)
      if (at instanceof HTMLDetailsElement) at.open = true
    if (!target.hasAttribute('tabindex')) target.tabIndex = -1
    target.scrollIntoView({ block: 'center' })
    target.focus({ preventScroll: true })
  }, [ready, hash])
}

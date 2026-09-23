import { expect } from 'vitest'

/**
 * 當前頁只由 TanStack 掛的 `aria-current` 與 `data-status` 說，不另外疊一組 class（M2 票 13）。
 *
 * `activeProps` 的 class 是**接在後面**的：當前那一格同時帶 `border-rule` 與 `border-rule-strong`，誰贏看 CSS 的
 * 產生順序。這個缺陷不在無障礙樹上（`aria-current` 照樣掛），所以這裡比的是兩格 class 的差：只能差 TanStack
 * 預設的 `active` 標記（沒有任何樣式掛在它上面），漆由 `NAV_LINK` 的 `data-[status=active]:` 換。
 */
export function expectCurrentByStateOnly(current: HTMLElement, other: HTMLElement) {
  expect(current).toHaveAttribute('aria-current', 'page')
  expect(current).toHaveAttribute('data-status', 'active')
  expect(other).not.toHaveAttribute('aria-current')
  expect([...current.classList].filter((name) => !other.classList.contains(name))).toEqual([
    'active',
  ])
}

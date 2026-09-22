import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test/render'
import { LanguageToggle } from './LanguageToggle'

/**
 * 票 03 第 11 條：語言是角色不是狀態，選中態不塗 `assigned`。
 *
 * DESIGN.md 的 The Role Is Not A State Rule 寫「角色、語言、分類……一律用中性色塊」，
 * 而黃漆的語意是「現在需要你」——頁首右上角常駐一塊黃，它什麼都不需要你做。
 */
describe('LanguageToggle', () => {
  function keys() {
    const all = screen.getAllByRole('button')
    return {
      current: all.filter((key) => key.getAttribute('aria-pressed') === 'true'),
      others: all.filter((key) => key.getAttribute('aria-pressed') === 'false'),
    }
  }

  it('選中的語言鍵用中性色塊，不用 assigned 黃漆', () => {
    renderWithProviders(<LanguageToggle />)
    const { current, others } = keys()

    expect(current).toHaveLength(1)
    expect(others.length).toBeGreaterThan(0)
    // 對著漆本身，不是對著任何含 `assigned` 的字（勾選框的 `accent-[var(--color-assigned)]`
    // 是合法用法，不該讓這條誤紅）。
    expect(current[0].className).not.toMatch(/\bbg-assigned\b/)
    expect(current[0].className).toMatch(/\bbg-deck\b/)
    expect(others[0].className).toMatch(/\bbg-well\b/)
  })

  it('哪一顆是選中的不只靠顏色：`aria-pressed` 自己說得出來', () => {
    renderWithProviders(<LanguageToggle />)
    const { current, others } = keys()

    // 兩顆中性色塊的差別只有明度，所以非顏色的那一層必須在（PRODUCT.md 的無障礙底線）。
    expect(current[0]).toHaveAttribute('aria-pressed', 'true')
    expect(others[0]).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('group')).toHaveAccessibleName()
  })
})

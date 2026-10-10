import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { ToggleChips } from './ToggleChips'
import { toggled } from './toggled'

/** 一組可多選的切換鍵（M4 票 83；票 84 的名字與季選擇也用它）。 */
describe('ToggleChips', () => {
  function Harness({ start = ['a'] }: { start?: string[] }) {
    const [selected, setSelected] = useState<ReadonlySet<string>>(new Set(start))
    return (
      <ToggleChips
        label="要列出哪幾類"
        chips={[
          { value: 'a', label: '符合', count: 13 },
          { value: 'b', label: '年份不符', count: 0 },
          { value: 'c', label: 'S01' },
        ]}
        selected={selected}
        onToggle={(value) => setSelected((before) => toggled(before, value))}
      />
    )
  }

  it('整組是一個有名字的 group，每一顆的名字帶著筆數', () => {
    render(<Harness />)

    const group = screen.getByRole('group', { name: '要列出哪幾類' })
    expect(group).toBeVisible()
    expect(screen.getByRole('button', { name: '符合 13' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '年份不符 0' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    // 沒給筆數的就只有標籤。
    expect(screen.getByRole('button', { name: 'S01' })).toBeVisible()
  })

  it('按一下開、再按一下關，可以多選', async () => {
    render(<Harness />)

    await userEvent.click(screen.getByRole('button', { name: 'S01' }))
    expect(screen.getByRole('button', { name: 'S01' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '符合 13' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: '符合 13' }))
    expect(screen.getByRole('button', { name: '符合 13' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('toggled 不改原本那一組', () => {
    const before = new Set(['a'])

    expect([...toggled(before, 'b')]).toEqual(['a', 'b'])
    expect([...toggled(before, 'a')]).toEqual([])
    expect([...before]).toEqual(['a'])
  })
})

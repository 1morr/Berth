import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { FilterBar } from './FilterBar'

function Bar({ counts }: { counts: { open: number; all: number } }) {
  return (
    <FilterBar
      label="篩選"
      options={[
        { value: 'open', label: `還沒了結 ${counts.open}` },
        { value: 'all', label: `全部 ${counts.all}` },
      ]}
      current="open"
      renderOption={(_, label) => <button type="button">{label}</button>}
    />
  )
}

describe('FilterBar', () => {
  it('選著的那一個是 aria-current 的字，不是按鈕或連結', () => {
    render(<Bar counts={{ open: 4, all: 5 }} />)

    expect(screen.getByRole('navigation', { name: '篩選' })).toBeInTheDocument()
    expect(screen.getByText('還沒了結 4')).toHaveAttribute('aria-current', 'true')
    expect(screen.queryByRole('button', { name: '還沒了結 4' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '全部 5' })).toBeInTheDocument()
  })

  it('件數即時更新時，鍵盤停在上面的那一顆不被換掉（code-review）', () => {
    const { rerender } = render(<Bar counts={{ open: 4, all: 5 }} />)
    const all = screen.getByRole('button', { name: '全部 5' })
    all.focus()

    rerender(<Bar counts={{ open: 4, all: 6 }} />)

    expect(screen.getByRole('button', { name: '全部 6' })).toBe(all)
    expect(all).toHaveFocus()
  })

  it('按了換選、那一顆變成字：焦點落在新選的那一格，不掉回頁面頂端（M5 票 15）', async () => {
    function Switch() {
      const [current, setCurrent] = useState<'week' | 'month'>('month')
      return (
        <FilterBar
          label="期間"
          options={[
            { value: 'week', label: '7 天' },
            { value: 'month', label: '30 天' },
          ]}
          current={current}
          renderOption={(value, label) => (
            <button type="button" onClick={() => setCurrent(value)}>
              {label}
            </button>
          )}
        />
      )
    }
    render(<Switch />)
    // 一開始畫出來的那一格不搶焦點。
    expect(screen.getByText('30 天')).not.toHaveFocus()

    await userEvent.click(screen.getByRole('button', { name: '7 天' }))

    expect(screen.getByText('7 天')).toHaveFocus()
  })
})

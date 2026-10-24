import { render, screen } from '@testing-library/react'
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
})

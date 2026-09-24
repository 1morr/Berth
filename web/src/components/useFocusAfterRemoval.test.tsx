import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { useFocusAfterRemoval } from './useFocusAfterRemoval'

function List({ initial }: { initial: string[] }) {
  const [rows, setRows] = useState(initial)
  const [note, setNote] = useState(false)
  const frame = useFocusAfterRemoval()
  return (
    <div ref={frame}>
      <h1 tabIndex={-1}>Queue</h1>
      <button type="button" onClick={() => setNote((shown) => !shown)}>
        toggle
      </button>
      {note && <p>unrelated</p>}
      {rows.map((row) => (
        <article key={row} tabIndex={-1} aria-label={row}>
          <button type="button" onClick={() => setRows((left) => left.filter((r) => r !== row))}>
            done {row}
          </button>
        </article>
      ))}
    </div>
  )
}

describe('useFocusAfterRemoval', () => {
  it('那一列被拿掉時，焦點落在接替它的那一列', async () => {
    render(<List initial={['a', 'b']} />)

    await userEvent.click(screen.getByRole('button', { name: 'done a' }))

    await waitFor(() => expect(screen.getByRole('article', { name: 'b' })).toHaveFocus())
  })

  // M2 票 16 的 audit：焦點進過某一列、之後使用者自己點到空白處（焦點回到 `body`），頁面上任何
  // 一次無關的變動都會把焦點拉回那一列、整頁捲過去。
  it('那一列還在時，無關的變動不會把焦點拉回去', async () => {
    render(<List initial={['a', 'b']} />)
    const done = screen.getByRole('button', { name: 'done a' })
    done.focus()
    done.blur()
    expect(document.body).toHaveFocus()

    screen.getByRole('button', { name: 'toggle' }).click()
    await screen.findByText('unrelated')

    expect(document.body).toHaveFocus()
  })
})

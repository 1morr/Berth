import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test/render'
import { CollapsibleRow } from './CollapsibleRow'

afterEach(() => {
  vi.restoreAllMocks()
})

function box(element: Element, top: number, bottom: number) {
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({
    top,
    bottom,
    left: 0,
    right: 390,
    width: 390,
    height: bottom - top,
    x: 0,
    y: top,
    toJSON: () => ({}),
  })
}

async function openRow() {
  renderWithProviders(
    <CollapsibleRow name="S01" summary={<span>S01</span>}>
      {() => (
        <select aria-label="assign">
          <option>S01E01</option>
        </select>
      )}
    </CollapsibleRow>,
  )
  await userEvent.click(screen.getByText('S01'))
  return {
    summary: screen.getByText('S01').closest('summary')!,
    field: screen.getByRole('combobox', { name: 'assign' }),
  }
}

describe('CollapsibleRow', () => {
  // M2 票 16 的 audit：390px 上反向 Tab 回到一個本來就在畫面內的欄位時瀏覽器不捲動，而它正好在黏頂的
  // 摘要列（y 0–113）底下——焦點整個被蓋住（WCAG 2.2 2.4.11）。`scroll-margin` 只在瀏覽器捲動時有用。
  it('焦點落在黏頂摘要列底下時，把畫面往回捲到露出它', async () => {
    const { summary, field } = await openRow()
    box(summary, 0, 113)
    box(field, 52, 94)
    const scroll = vi.spyOn(window, 'scrollBy').mockImplementation(() => {})

    field.focus()

    expect(scroll).toHaveBeenCalledOnce()
    // 捲回被蓋住的那 61px，再多留焦點環那一點。
    expect(scroll).toHaveBeenCalledWith({ top: -(113 - 52 + 8) })
  })

  it('沒有被蓋住就不動畫面', async () => {
    const { summary, field } = await openRow()
    box(summary, 0, 113)
    box(field, 200, 242)
    const scroll = vi.spyOn(window, 'scrollBy').mockImplementation(() => {})

    field.focus()

    expect(scroll).not.toHaveBeenCalled()
  })
})

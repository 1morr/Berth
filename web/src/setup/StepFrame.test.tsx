import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { StepFrame } from './StepFrame'

/** 這一步自己的 state：按下「套用」之後那顆鍵換成「前往下一個泊位」。StepFrame 本身不重繪。 */
function Apply() {
  const [done, setDone] = useState(false)
  return done ? (
    // 不同的 key：換成另一個 DOM 節點，與精靈裡整塊換掉的情況一樣（同一位置同一種元素 React 會重用）。
    <button key="next" type="button" data-berth-next>
      前往下一個泊位
    </button>
  ) : (
    <button key="apply" type="button" onClick={() => setDone(true)}>
      套用這 5 個鍵
    </button>
  )
}

/** 一段會自己變的說明（輪詢回來的數字之類）：DOM 在變，但沒有東西被拿掉。 */
function Hint() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen((was) => !was)}>
        說明
      </button>
      {open && <p>多一段說明</p>}
    </>
  )
}

function Step() {
  return (
    <StepFrame cutaway={<h3>剖面</h3>}>
      <h2>套用</h2>
      <Apply />
      <Hint />
    </StepFrame>
  )
}

describe('StepFrame 的焦點', () => {
  it('掛上時焦點在這一步的標題', async () => {
    render(<Step />)
    await waitFor(() => expect(screen.getByRole('heading', { name: '套用' })).toHaveFocus())
  })

  /** code review（票 06h）：原本靠 StepFrame 自己重繪時才檢查，這一步自己換鍵時接不回來。 */
  it('按下的鍵被換掉時，焦點接到「前往下一個泊位」，StepFrame 自己沒有重繪也一樣', async () => {
    const user = userEvent.setup()
    render(<Step />)

    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '前往下一個泊位' })).toHaveFocus(),
    )
  })

  it('使用者自己讓焦點回到 body（上一個有焦點的還在），DOM 再怎麼變都不搶', async () => {
    const user = userEvent.setup()
    render(<Step />)
    const hint = screen.getByRole('button', { name: '說明' })
    await user.click(hint)
    hint.blur()

    // 不帶焦點的點擊：只讓 DOM 變一次。
    expect(screen.getByText('多一段說明')).toBeInTheDocument()
    fireEvent.click(hint)
    await waitFor(() => expect(screen.queryByText('多一段說明')).not.toBeInTheDocument())
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(document.activeElement).toBe(document.body)
  })
})

/**
 * 第二件事放在剖面底下（M4 票 119）：桌機頁 4 套件內的介面登入。DOM 在工作面之後、剖面之前不行——剖面
 * 是唯讀的、Tab 到它之前先到要填的那一區；所以它在剖面那一欄、接在剖面後面，而那一欄不再固定。
 */
describe('StepFrame 的 aside', () => {
  it('在剖面那一欄、剖面之後；那一欄不固定（剖面固定時會蓋住它）', () => {
    render(
      <StepFrame cutaway={<h3>剖面</h3>} aside={<section aria-label="第二件事" />}>
        <h2>工作</h2>
      </StepFrame>,
    )

    const cutaway = screen.getByRole('heading', { name: '剖面' })
    const aside = screen.getByRole('region', { name: '第二件事' })
    const column = cutaway.closest('[data-frame-column]')
    expect(column).not.toBeNull()
    expect(column).toContainElement(aside)
    expect(column).not.toContainElement(screen.getByRole('heading', { name: '工作' }))
    expect(cutaway.compareDocumentPosition(aside) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(column?.querySelector('[class*="sticky"]')).toBeNull()
  })

  it('沒有 aside 時剖面照舊固定', () => {
    render(
      <StepFrame cutaway={<h3>剖面</h3>}>
        <h2>工作</h2>
      </StepFrame>,
    )

    const column = screen.getByRole('heading', { name: '剖面' }).closest('[data-frame-column]')
    expect(column?.querySelector('[class*="lg:sticky"]')).not.toBeNull()
  })
})

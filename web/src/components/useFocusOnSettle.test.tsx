import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useFocusOnSettle } from './useFocusOnSettle'

/** 一顆做完就消失的鍵與說結果的那一格，加一個別處的輸入框。 */
function Card({ settled }: { settled: boolean }) {
  const status = useFocusOnSettle<HTMLParagraphElement>(settled)
  return (
    <>
      <input aria-label="別處" />
      {!settled && <button type="button">確認</button>}
      <p ref={status} tabIndex={-1}>
        {settled ? '做好了' : ''}
      </p>
    </>
  )
}

describe('useFocusOnSettle', () => {
  it('鍵做完消失、焦點掉了：落在說結果的那一格', () => {
    const { rerender } = render(<Card settled={false} />)
    screen.getByRole('button', { name: '確認' }).focus()

    rerender(<Card settled />)

    expect(screen.getByText('做好了')).toHaveFocus()
  })

  it('焦點在別處（使用者在打字）時不搶', () => {
    const { rerender } = render(<Card settled={false} />)
    screen.getByRole('textbox', { name: '別處' }).focus()

    rerender(<Card settled />)

    expect(screen.getByRole('textbox', { name: '別處' })).toHaveFocus()
  })

  it('一開始就做好了（重整之後畫出來的舊卡）不給', () => {
    render(<Card settled />)

    expect(screen.getByText('做好了')).not.toHaveFocus()
  })
})

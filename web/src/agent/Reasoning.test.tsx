import { render, screen } from '@testing-library/react'
import type { ReasoningUIPart } from 'ai'
import { describe, expect, it } from 'vitest'

import { Reasoning } from './Reasoning'

const TEXT = '使用者想知道下載為什麼還沒完成。\n最後一行：直接回答。'

function part(state: ReasoningUIPart['state'], text = TEXT): ReasoningUIPart {
  return { type: 'reasoning', text, state }
}

/** 收起的 `<details>` 裡的字仍在 DOM 裡，只是看不到：以 `open` 判斷收起與否。 */
function details(): HTMLDetailsElement {
  const found = screen.getByText('推理').closest('details')
  if (found === null) throw new Error('no <details> around the reasoning')
  return found
}

describe('Reasoning (M5.5 ticket 16)', () => {
  it('starts folded and holds the whole text', () => {
    render(<Reasoning part={part('done')} live={false} />)
    expect(details().open).toBe(false)
    expect(details()).toHaveTextContent('最後一行：直接回答。')
    expect(screen.queryByText('思考中')).toBeNull()
  })

  it('stays folded while it streams, and says it is still thinking', () => {
    const { rerender } = render(<Reasoning part={part('streaming', '使用者想知道')} live />)
    expect(details().open).toBe(false)
    expect(screen.getByText('思考中')).toBeInTheDocument()

    rerender(<Reasoning part={part('streaming')} live />)
    expect(details().open).toBe(false)
  })

  it('drops "thinking" once the turn is over, even if the part never left streaming (M5.5 ticket 19)', () => {
    // 前端按「停止」中止串流時，這一段停在 `streaming`：色塊不能一直掛在結束的那一則上。
    render(<Reasoning part={part('streaming', '使用者想知道')} live={false} />)
    expect(screen.queryByText('思考中')).toBeNull()
  })

  it('stays open once the reader opened it, while more text arrives', () => {
    const { rerender } = render(<Reasoning part={part('streaming', '使用者想知道')} live />)
    details().open = true

    rerender(<Reasoning part={part('done')} live={false} />)
    expect(details().open).toBe(true)
    expect(details()).toHaveTextContent('最後一行：直接回答。')
  })

  it('draws nothing for reasoning without text (a redacted block)', () => {
    const { container } = render(<Reasoning part={part('done', '')} live={false} />)
    expect(container).toBeEmptyDOMElement()
  })
})

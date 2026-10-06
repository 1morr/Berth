import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { BerthBoard, type BoardSlot } from './BerthBoard'

const SLOTS: BoardSlot[] = [
  { code: 'BTH 1', name: 'Jellyfin', status: '已繫上', signal: 'secured', selectable: true },
  { code: 'BTH 2', name: 'qBittorrent', status: '阻擋', signal: 'blocked', selectable: true },
  { code: 'BTH 3', name: '媒體庫路徑', status: '待靠泊', signal: 'assigned', selectable: true },
  { code: 'BTH 4', name: 'Prowlarr', status: '未指派', signal: 'neutral', filled: false },
  { code: 'BTH 5', name: 'TMDB', status: '未指派', signal: 'neutral', filled: false },
]

const WORDS = { expand: '展開', collapse: '收起', blocked: '阻擋' }

/** 窄版的那一列摘要（M4 票 30，`.scratch/m4/wizard-navigation-shape.md`）。CSS 不在 jsdom 裡：
 *  收起是 `hidden sm:grid`（窄版不畫、桌機照舊），所以看的是類名與 `aria-expanded`。 */
describe('窄版的摘要列', () => {
  function summary() {
    return screen.getByRole('button', { name: /展開|收起/ })
  }

  it('收著時五格的清單在窄版不畫、桌機照舊；摘要說出目前那一格與它的狀態', () => {
    render(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 3" summary={WORDS} />)

    expect(summary()).toHaveAttribute('aria-expanded', 'false')
    expect(summary()).toHaveTextContent(/BTH 3.*媒體庫路徑.*待靠泊/)
    const list = screen.getByRole('list', { hidden: true })
    expect(summary()).toHaveAttribute('aria-controls', list.id)
    expect(list).toHaveClass('hidden', 'sm:grid')
  })

  it('紅了的其他格用字說出來，不只靠小色塊的顏色', () => {
    render(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 3" summary={WORDS} />)

    expect(summary()).toHaveTextContent('阻擋 BTH 2')
  })

  it('目前那一格自己紅了，阻擋那一行不重複說它', () => {
    render(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 2" summary={WORDS} />)

    expect(summary()).not.toHaveTextContent(/阻擋 BTH/)
  })

  it('按了展開整塊板，再按收起', async () => {
    const user = userEvent.setup()
    render(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 3" summary={WORDS} />)

    await user.click(summary())
    expect(summary()).toHaveAttribute('aria-expanded', 'true')
    expect(summary()).toHaveTextContent('收起')
    expect(screen.getByRole('list')).not.toHaveClass('hidden')

    await user.click(summary())
    expect(summary()).toHaveAttribute('aria-expanded', 'false')
  })

  it('換到另一格就收起（每次進頁收起、不記）', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <BerthBoard label="泊位板" slots={SLOTS} current="BTH 3" summary={WORDS} />,
    )
    await user.click(summary())

    rerender(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 1" summary={WORDS} />)

    expect(summary()).toHaveAttribute('aria-expanded', 'false')
    expect(summary()).toHaveTextContent(/BTH 1.*Jellyfin/)
  })

  /** code-review 抓到：記的是在哪一格展開的，瀏覽器的上一頁回到那一格時又是展開的。 */
  it('回到展開過的那一格也是收著的', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <BerthBoard label="泊位板" slots={SLOTS} current="BTH 1" summary={WORDS} />,
    )
    await user.click(summary())

    rerender(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 2" summary={WORDS} />)
    rerender(<BerthBoard label="泊位板" slots={SLOTS} current="BTH 1" summary={WORDS} />)

    expect(summary()).toHaveAttribute('aria-expanded', 'false')
  })

  it('沒有目前那一格（完成頁）就說板的名字', () => {
    render(<BerthBoard label="泊位板" slots={SLOTS} summary={WORDS} />)

    // 小色塊的號碼也在 textContent 裡（它們 `aria-hidden`）；板名緊接在後，沒有哪一格的名字。
    expect(summary()).toHaveTextContent(/12345泊位板/)
  })

  it('健康頁不給摘要：沒有展開鍵，五格一直都在', () => {
    render(<BerthBoard label="泊位板" slots={SLOTS} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('list')).not.toHaveClass('hidden')
  })
})

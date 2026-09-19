import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test/render'
import { FileEntry } from './FileEntry'

function entry(inside: 'bare' | 'open group' = 'bare') {
  const row = (
    <ol>
      <FileEntry summary={<span>S01E01</span>}>
        <p>/data/library/anime/Frieren/Season 01/Frieren - S01E01.mkv</p>
      </FileEntry>
    </ol>
  )
  return renderWithProviders(
    inside === 'bare' ? (
      row
    ) : (
      // 逐檔列真正長的地方：下載列那一筆（`JobRow` 帶 `group`）與季的收合區，兩者展開時才看得到它。
      <details className="group" open>
        <summary>下載列那一筆</summary>
        {row}
      </details>
    ),
  )
}

describe('FileEntry（M1.5 票 09b）', () => {
  it('收起時路徑不可見，展開才有', async () => {
    entry()

    expect(screen.queryByText(/Frieren - S01E01\.mkv/)).not.toBeVisible()

    await userEvent.click(screen.getByText('S01E01'))

    expect(screen.getByText(/Frieren - S01E01\.mkv/)).toBeVisible()
  })

  it('提示說的是自己的開合，不是外層那一個 `<details>` 的（`group-open:` 匹配任一個祖先）', async () => {
    entry('open group')

    // 外層是展開的，但這一列自己是收起的——提示只能說「展開」，而且 DOM 裡不能同時有兩份
    // （`ExpandHint` 的 CSS 那一種會把兩份都畫出來，靠 `group-open:` 藏掉其中一份）。
    const row = screen.getByRole('listitem')
    expect(within(row).getByText('展開')).toBeInTheDocument()
    expect(within(row).queryByText('收起')).not.toBeInTheDocument()

    await userEvent.click(within(row).getByText('S01E01'))

    expect(within(row).getByText('收起')).toBeInTheDocument()
    expect(within(row).queryByText('展開')).not.toBeInTheDocument()
  })
})

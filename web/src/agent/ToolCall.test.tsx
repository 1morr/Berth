import { render, screen, within } from '@testing-library/react'
import type { DynamicToolUIPart } from 'ai'
import { describe, expect, it } from 'vitest'

import { ToolCall } from './ToolCall'

function done(toolName: string, output: unknown = { results: [] }): DynamicToolUIPart {
  return {
    type: 'dynamic-tool',
    toolName,
    toolCallId: 'call1',
    state: 'output-available',
    input: { query: 'Re:Zero 評價' },
    output,
  }
}

describe('ToolCall', () => {
  it('names the web searches added in ticket 17', () => {
    render(<ToolCall part={done('web_tavily_search')} />)
    expect(screen.getByText('網路搜尋（Tavily）')).toBeInTheDocument()
  })

  it('prints a tool it does not know by its own name', () => {
    render(<ToolCall part={done('anilist_search')} />)
    expect(screen.getByText('anilist_search')).toBeInTheDocument()
  })

  it('names the RSS tools added in ticket 14', () => {
    render(<ToolCall part={done('rss_add_feed')} />)
    expect(screen.getByText('新增 RSS Feed')).toBeInTheDocument()
  })

  it('a call Berth refused is not done, although it has a result', () => {
    // 守法擋下的呼叫（票 14）：結果是給模型的理由，不是做成了。
    render(
      <ToolCall
        part={done('rss_add_feed', {
          refused: 'address_not_from_user',
          detail: 'not typed by the user',
        })}
      />,
    )
    expect(screen.getByText('沒成功')).toBeInTheDocument()
    expect(screen.queryByText('完成')).toBeNull()
  })

  describe('web_search (M5.5 ticket 03)', () => {
    const results = [
      {
        type: 'web_search_result',
        title: 'Frieren: Beyond Journey’s End season 2',
        url: 'https://en.wikipedia.org/wiki/Frieren',
        page_age: 'October 3, 2026',
      },
      {
        type: 'web_search_result',
        title: 'Frieren S2 review',
        url: 'https://www.animenewsnetwork.com/review/frieren-s2',
      },
    ]

    it('lists each result by title, address and date instead of the raw JSON', () => {
      render(<ToolCall part={done('web_search', results)} />)
      const list = screen.getByRole('list', { name: '結果' })
      const [first, second] = within(list).getAllByRole('listitem')
      const link = within(first).getByRole('link', {
        name: 'Frieren: Beyond Journey’s End season 2',
      })
      expect(link).toHaveAttribute('href', 'https://en.wikipedia.org/wiki/Frieren')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
      expect(first).toHaveTextContent('https://en.wikipedia.org/wiki/Frieren')
      expect(first).toHaveTextContent('October 3, 2026')
      // 沒有 `page_age` 的照樣列，不印空的日期。
      expect(second).toHaveTextContent('Frieren S2 review')
      expect(second.children).toHaveLength(2)
      expect(screen.queryByText(/web_search_result/)).toBeNull()
    })

    it('does not link an address the markdown would not link either', () => {
      render(<ToolCall part={done('web_search', [{ title: 'Odd', url: 'javascript:alert(1)' }])} />)
      expect(screen.queryByRole('link')).toBeNull()
      expect(screen.getByText('Odd')).toBeInTheDocument()
    })

    it('says so when the search found nothing', () => {
      render(<ToolCall part={done('web_search', [])} />)
      expect(screen.getByText('沒有搜到網頁')).toBeInTheDocument()
    })

    it('a search the service turned down did not work, and shows its error code', () => {
      render(
        <ToolCall
          part={done('web_search', {
            type: 'web_search_tool_result_error',
            error_code: 'max_uses_exceeded',
          })}
        />,
      )
      expect(screen.getByText('沒成功')).toBeInTheDocument()
      expect(screen.getByText(/max_uses_exceeded/)).toBeInTheDocument()
    })

    it('other tools still print their result as is', () => {
      render(<ToolCall part={done('web_tavily_search', results)} />)
      expect(screen.queryByRole('list', { name: '結果' })).toBeNull()
      expect(screen.getByText(/web_search_result/)).toBeInTheDocument()
    })
  })
})

import { render, screen } from '@testing-library/react'
import type { DynamicToolUIPart } from 'ai'
import { describe, expect, it } from 'vitest'

import { renderInRoute } from '../test/render'
import { AgentProvider } from './AgentProvider'
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
})

describe('ToolCall for a feed the assistant subscribed by itself', () => {
  // `rss.subscribe_search` 不出卡、直接建（可逆，plan §11.6）；撤銷在 RSS 頁那一列（M5 票 22）。
  function renderFeed(part: DynamicToolUIPart) {
    return renderInRoute(
      <AgentProvider>
        <ToolCall part={part} />
      </AgentProvider>,
      '/library',
    )
  }

  it('links to its row on the RSS page, where the first round is chosen or it is deleted', async () => {
    renderFeed(done('rss_subscribe_search', { id: 7, title: 'SPY×FAMILY 1080p' }))

    const link = await screen.findByRole('link', { name: '到 RSS 頁那一列' })
    expect(link).toHaveAttribute('href', '/rss#feed-7')
    expect(screen.getByText(/還沒開始下載/)).toBeInTheDocument()
  })

  it('finds the feed when the result came wrapped with a warning', async () => {
    renderFeed(done('rss_subscribe_search', { result: { id: 9 }, warning: 'identical call' }))

    expect(await screen.findByRole('link', { name: '到 RSS 頁那一列' })).toHaveAttribute(
      'href',
      '/rss#feed-9',
    )
  })

  it('has no link when nothing was made', async () => {
    renderFeed(done('rss_subscribe_search', { refused: 'rss_disabled', detail: '' }))

    expect(await screen.findByText('沒成功')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })
})

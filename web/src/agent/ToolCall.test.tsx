import { render, screen } from '@testing-library/react'
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
})

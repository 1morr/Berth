import { render, screen } from '@testing-library/react'
import type { DynamicToolUIPart } from 'ai'
import { describe, expect, it } from 'vitest'

import { ToolCall } from './ToolCall'

function done(toolName: string): DynamicToolUIPart {
  return {
    type: 'dynamic-tool',
    toolName,
    toolCallId: 'call1',
    state: 'output-available',
    input: { query: 'Re:Zero 評價' },
    output: { results: [] },
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
})

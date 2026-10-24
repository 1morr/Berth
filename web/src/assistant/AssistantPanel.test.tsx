import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssistantStatus, Conversation } from '../api/assistant'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'
import { held, streamed } from '../test/sse'

/**
 * 側面板（M5 票 08，`.scratch/m5/side-panel-shape.md`）。從頁首的「助理」鍵進去，斷言畫面上讀得到的字；
 * 後端是 `stubApi`，串流是 `test/sse.ts` 的替身。
 */

const ADMIN = { name: 'skipper', role: 'admin' }
const CREW = { name: 'deckhand', role: 'user' }
const READY: AssistantStatus = { ready: true, chat_only: false }
const AT = '2026-10-24T12:00:00Z'

function conversation(id: number, messages: Conversation['messages']): Conversation {
  return { id, title: 'hi', created_at: AT, updated_at: AT, replying: false, messages }
}

const SAVED = conversation(7, [
  { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: '這週入庫了什麼' }] },
  {
    id: 2,
    kind: 'model',
    created_at: AT,
    parts: [{ type: 'model_text', text: '這週入庫了兩部。' }],
  },
])

function render({
  me = ADMIN,
  status = READY,
  routes = {},
}: { me?: object; status?: AssistantStatus; routes?: StubRoutes } = {}) {
  const stub = stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: me },
    'GET /api/assistant': { body: status },
    'GET /api/conversations': { body: [] },
    ...routes,
  })
  renderApp('/')
  return stub
}

async function openPanel() {
  await userEvent.click(await screen.findByRole('button', { name: '助理' }))
  return screen.findByRole('complementary', { name: '助理' })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('沒設好 AI', () => {
  it('管理員看到去設定', async () => {
    render({ status: { ready: false, chat_only: false } })

    const panel = await openPanel()

    expect(await within(panel).findByText('AI 還沒設定好。')).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: '去設定' })).toHaveAttribute(
      'href',
      '/settings/ai',
    )
    expect(within(panel).queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('一般使用者看到管理員還沒開啟', async () => {
    render({ me: CREW, status: { ready: false, chat_only: false } })

    const panel = await openPanel()

    expect(await within(panel).findByText('管理員還沒開啟 AI。')).toBeInTheDocument()
    expect(within(panel).queryByRole('link', { name: '去設定' })).not.toBeInTheDocument()
  })
})

describe('送一句話', () => {
  it('字一段一段串流出來，講完之後畫的是重讀到的那一份', async () => {
    const reply = held()
    let saved = false
    const stub = render({
      routes: {
        'POST /api/conversations': () => {
          saved = true
          return reply.respond()
        },
        'GET /api/conversations/7': () => ({
          body: saved
            ? conversation(7, [
                ...SAVED.messages.slice(0, 1),
                {
                  id: 2,
                  kind: 'model',
                  created_at: AT,
                  parts: [{ type: 'model_text', text: '這週入庫了兩部。' }],
                },
              ])
            : conversation(7, []),
        }),
      },
    })
    const panel = await openPanel()

    // 打開時焦點在輸入框（shape 第 6 節）。
    const input = within(panel).getByRole('textbox', { name: '跟助理說' })
    expect(input).toHaveFocus()
    await userEvent.type(input, '這週入庫了什麼{Enter}')
    reply.push({ type: 'start', conversation_id: 7 })
    reply.push({ type: 'text-delta', delta: '這週入庫' })

    const log = within(panel).getByRole('log')
    expect(await within(log).findByText('這週入庫')).toBeInTheDocument()
    expect(within(log).getByText('這週入庫了什麼')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: '回覆中…' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )

    reply.push({ type: 'text-delta', delta: '了兩部。' })
    reply.push({ type: 'finish' })

    expect(await within(log).findByText('這週入庫了兩部。')).toBeInTheDocument()
    await waitFor(() =>
      expect(within(panel).getByRole('button', { name: '送出' })).not.toHaveAttribute(
        'aria-disabled',
      ),
    )
    // 介面語言跟著送出去，回覆用它。
    const sent = stub.mock.calls.find(
      ([url, init]) => url === '/api/conversations' && init?.method === 'POST',
    )
    expect(JSON.parse(String(sent?.[1]?.body))).toEqual({
      text: '這週入庫了什麼',
      language: 'zh-Hant',
    })
  })

  it('工具呼叫時說正在查，跑完說查過', async () => {
    const reply = held()
    render({
      routes: {
        'POST /api/conversations': () => reply.respond(),
        'GET /api/conversations/7': { body: conversation(7, []) },
      },
    })
    const panel = await openPanel()
    await userEvent.type(within(panel).getByRole('textbox'), '這週入庫了什麼{Enter}')

    reply.push({ type: 'start', conversation_id: 7 })
    reply.push({ type: 'tool-input-start', tool_call_id: 'c1', tool_name: 'recent_imports' })
    expect(await within(panel).findByText('正在查最近入庫')).toBeInTheDocument()
    expect(within(panel).getByText('查詢中')).toBeInTheDocument()

    reply.push({
      type: 'tool-output-available',
      tool_call_id: 'c1',
      tool_name: 'recent_imports',
      outcome: 'done',
    })
    expect(await within(panel).findByText('查過最近入庫')).toBeInTheDocument()
    reply.push({ type: 'finish' })
  })

  it('被限流時說得出幾秒後再送，重讀之後還在', async () => {
    const limited = {
      type: 'notice',
      notice: 'provider_failed',
      failure: 'rate_limited',
      retry_after: 30,
    } as const
    render({
      routes: {
        'POST /api/conversations': streamed(
          { type: 'start', conversation_id: 7 },
          { type: 'notice', notice: limited },
          { type: 'finish' },
        ),
        'GET /api/conversations/7': {
          body: conversation(7, [
            { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: 'hi' }] },
            { id: 2, kind: 'notice', created_at: AT, parts: [limited] },
          ]),
        },
      },
    })
    const panel = await openPanel()

    await userEvent.type(within(panel).getByRole('textbox'), 'hi{Enter}')

    expect(await within(panel).findByText(/30 秒後再送/)).toBeInTheDocument()
    expect(within(panel).getByText('等一下')).toBeInTheDocument()
  })

  it('上一個回覆還在跑時就地說，不清掉打好的字', async () => {
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': { body: SAVED },
        'POST /api/conversations/7/messages': {
          status: 409,
          body: { detail: { reason: 'busy', detail: '7' } },
        },
      },
    })
    const panel = await openPanel()
    const input = await within(panel).findByRole('textbox')

    await userEvent.type(input, '快一點{Enter}')

    expect(await within(panel).findByText('上一個回覆還在跑，等它講完再送。')).toBeInTheDocument()
    expect(input).toHaveValue('快一點')
  })
})

describe('存下來的', () => {
  it('重整之後面板照樣開著，畫出最近那一則', async () => {
    localStorage.setItem('berth.assistant.open', '1')
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': { body: SAVED },
      },
    })

    const panel = await screen.findByRole('complementary', { name: '助理' })

    expect(await within(panel).findByText('這週入庫了兩部。')).toBeInTheDocument()
    // 照記憶打開的不搶焦點。
    expect(within(panel).getByRole('textbox')).not.toHaveFocus()
  })

  it('歷史清單挑一則就回到那一則', async () => {
    render({
      routes: {
        'GET /api/conversations': {
          body: [
            { id: 8, title: '最新的', updated_at: AT },
            { id: 7, title: '這週入庫了什麼', updated_at: AT },
          ],
        },
        'GET /api/conversations/8': { body: conversation(8, []) },
        'GET /api/conversations/7': { body: SAVED },
      },
    })
    const panel = await openPanel()

    await userEvent.click(within(panel).getByRole('button', { name: '歷史' }))
    await userEvent.click(await within(panel).findByRole('button', { name: /這週入庫了什麼/ }))

    expect(await within(panel).findByText('這週入庫了兩部。')).toBeInTheDocument()
  })

  it('別的工具結果還沒有卡片時，模型說做了也不畫成成功', async () => {
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': {
          body: conversation(7, [
            { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: '訂閱' }] },
            {
              id: 2,
              kind: 'model',
              created_at: AT,
              parts: [{ type: 'model_text', text: '好的，已訂閱。' }],
            },
          ]),
        },
      },
    })
    const panel = await openPanel()

    const said = await within(panel).findByText('好的，已訂閱。')

    // 模型的字是散文：沒有塗漆、不是狀態色塊。
    expect(said.className).not.toMatch(/bg-(secured|assigned|working|blocked)/)
    expect(panel.querySelector('.bg-secured')).toBeNull()
  })
})

describe('只能聊天', () => {
  it('標明這個模型只能聊天，輸入框照常', async () => {
    render({ status: { ready: true, chat_only: true } })

    const panel = await openPanel()

    expect(
      await within(panel).findByText('這個模型只能聊天：它說的事都沒有真的做。'),
    ).toBeInTheDocument()
    expect(within(panel).getByRole('textbox')).toBeInTheDocument()
  })
})

describe('開與關', () => {
  it('關閉之後焦點回到頁首的助理鍵，重整也記得是關的', async () => {
    render()
    const panel = await openPanel()

    await userEvent.click(within(panel).getByRole('button', { name: '關閉' }))

    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: '助理' })
    expect(toggle).toHaveFocus()
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(localStorage.getItem('berth.assistant.open')).toBe('0')
  })

  it('Esc 也關得掉', async () => {
    render()
    await openPanel()

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssistantStatus, Conversation, ProposalCard, RecentImports } from '../api/assistant'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'
import { held, streamed } from '../test/sse'

/**
 * 側面板（M5 票 08，`.scratch/m5/side-panel-shape.md`）。從頁首的「助理」鍵進去，斷言畫面上讀得到的字；
 * 後端是 `stubApi`，串流是 `test/sse.ts` 的替身。
 */

const ADMIN = { name: 'skipper', role: 'admin' }
const CREW = { name: 'deckhand', role: 'user' }
const READY: AssistantStatus = { ready: true, chat_only: false, tools: [] }
const AT = '2026-10-24T12:00:00Z'

function conversation(id: number, messages: Conversation['messages']): Conversation {
  return {
    id,
    title: 'hi',
    created_at: AT,
    updated_at: AT,
    replying: false,
    messages,
    proposals: [],
  }
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

/** 「最近入庫」的結果（後端 `services/tools.RecentImports`）：芙莉蓮四集、沙丘一部。 */
const THIS_WEEK: RecentImports = {
  since: '2026-10-17T12:00:00Z',
  until: '2026-10-24T12:00:00Z',
  works: [
    {
      media: 'tv:209867',
      kind: 'tv',
      title: '葬送的芙莉蓮',
      title_en: "Frieren: Beyond Journey's End",
      year: 2023,
      poster_url: 'https://image.tmdb.org/t/p/w342/zh.jpg',
      poster_url_en: 'https://image.tmdb.org/t/p/w342/en.jpg',
      episodes: [
        [1, 1, 3],
        [1, 5, 5],
      ],
      presence: 'searching',
    },
    {
      media: 'movie:693134',
      kind: 'movie',
      title: '沙丘：第二部',
      title_en: 'Dune: Part Two',
      year: 2024,
      poster_url: '',
      poster_url_en: '',
      episodes: [],
      presence: 'lost',
    },
  ],
}

/** 問了「這週入庫了什麼」、呼叫了「最近入庫」、回了一句話，存下來的那幾則。 */
function askedThisWeek(resultType: string, result: Record<string, unknown>): Conversation {
  return conversation(7, [
    { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: '這週入庫了什麼' }] },
    {
      id: 2,
      kind: 'model',
      created_at: AT,
      parts: [{ type: 'tool_call', id: 'c1', name: 'recent_imports', arguments: '{}' }],
    },
    {
      id: 3,
      kind: 'tools',
      created_at: AT,
      parts: [
        {
          type: 'tool_result',
          call_id: 'c1',
          tool: 'recent_imports',
          outcome: 'done',
          result_type: resultType,
          result,
        },
      ],
    },
    {
      id: 4,
      kind: 'model',
      created_at: AT,
      parts: [{ type: 'model_text', text: '這週入庫了兩部。' }],
    },
  ])
}

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
    render({ status: { ready: false, chat_only: false, tools: [] } })

    const panel = await openPanel()

    expect(await within(panel).findByText('AI 還沒設定好。')).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: '去設定' })).toHaveAttribute(
      'href',
      '/settings/ai',
    )
    expect(within(panel).queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('一般使用者看到管理員還沒開啟', async () => {
    render({ me: CREW, status: { ready: false, chat_only: false, tools: [] } })

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
    // 介面語言跟著送出去，回覆用它；畫面在哪一頁也是（作品頁時模型知道「這部」是哪一部，M5 票 12）。
    const sent = stub.mock.calls.find(
      ([url, init]) => url === '/api/conversations' && init?.method === 'POST',
    )
    expect(JSON.parse(String(sent?.[1]?.body))).toEqual({
      text: '這週入庫了什麼',
      language: 'zh-Hant',
      page: '/',
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
      result_type: 'RecentImports',
      result: { ...THIS_WEEK, works: [] },
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
    // 標出正在看的那一則（最近那一則），M5 票 15。
    expect(await within(panel).findByRole('button', { name: /最新的/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(within(panel).getByRole('button', { name: /這週入庫了什麼/ })).not.toHaveAttribute(
      'aria-current',
    )
    await userEvent.click(await within(panel).findByRole('button', { name: /這週入庫了什麼/ }))

    expect(await within(panel).findByText('這週入庫了兩部。')).toBeInTheDocument()
    // 清單那一列消失了：焦點回輸入框，不掉到頁面頂端（M5 票 15）。
    expect(within(panel).getByRole('textbox')).toHaveFocus()
  })

  it('沒有工具結果時，模型說做了也不畫成成功', async () => {
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

describe('結果卡', () => {
  /** 卡片一部一列：作品名連到作品頁，入庫的集與 Jellyfin 收錄了沒。 */
  async function expectThisWeekCard(panel: HTMLElement) {
    const card = await within(panel).findByRole('region', { name: '最近 7 天入庫' })
    expect(within(card).getByText(/2 部/)).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: '葬送的芙莉蓮' })).toHaveAttribute(
      'href',
      '/media/tv%3A209867',
    )
    expect(within(card).getByText('S01E01–E03, E05')).toBeInTheDocument()
    expect(within(card).getByText('等 Jellyfin 收錄')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: '沙丘：第二部' })).toBeInTheDocument()
    expect(within(card).getByText('Jellyfin 找不到它')).toBeInTheDocument()
    return card
  }

  it('問這週入庫了什麼：串流時就畫出作品卡，重讀之後畫的是存下的那一份', async () => {
    const reply = held()
    let saved = false
    render({
      routes: {
        'POST /api/conversations': () => {
          saved = true
          return reply.respond()
        },
        'GET /api/conversations/7': () => ({
          body: saved ? askedThisWeek('RecentImports', THIS_WEEK) : conversation(7, []),
        }),
      },
    })
    const panel = await openPanel()
    await userEvent.type(within(panel).getByRole('textbox'), '這週入庫了什麼{Enter}')

    reply.push({ type: 'start', conversation_id: 7 })
    reply.push({ type: 'tool-input-start', tool_call_id: 'c1', tool_name: 'recent_imports' })
    reply.push({
      type: 'tool-output-available',
      tool_call_id: 'c1',
      tool_name: 'recent_imports',
      outcome: 'done',
      result_type: 'RecentImports',
      result: THIS_WEEK,
    })
    await expectThisWeekCard(panel)

    reply.push({ type: 'text-delta', delta: '這週入庫了兩部。' })
    reply.push({ type: 'finish' })
    await waitFor(() =>
      expect(within(panel).getByRole('button', { name: '送出' })).not.toHaveAttribute(
        'aria-disabled',
      ),
    )
    await expectThisWeekCard(panel)
    expect(within(panel).getAllByRole('region', { name: '最近 7 天入庫' })).toHaveLength(1)
  })

  it('重整之後卡片照樣畫得出來：結果存在訊息裡，不重新查', async () => {
    const stub = render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': { body: askedThisWeek('RecentImports', THIS_WEEK) },
      },
    })
    const panel = await openPanel()

    const card = await expectThisWeekCard(panel)
    // 海報照 UI 語言挑；沒有海報的那一格說無海報、高度不變。
    expect(card.querySelector('img')).toHaveAttribute(
      'src',
      'https://image.tmdb.org/t/p/w342/zh.jpg',
    )
    expect(within(card).getByText('無海報')).toBeInTheDocument()
    expect(within(panel).getByText('這週入庫了兩部。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => String(url).startsWith('/api/weekly'))).toBe(false)
  })

  it('沒有入庫的那一段說沒有', async () => {
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': {
          body: askedThisWeek('RecentImports', { ...THIS_WEEK, works: [] }),
        },
      },
    })
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '最近 7 天入庫' })
    expect(within(card).getByText('這段時間沒有入庫。')).toBeInTheDocument()
  })

  it('認不得的結果型別只剩摘要，不丟錯', async () => {
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': { body: askedThisWeek('SomethingRemoved', { works: 3 }) },
      },
    })
    const panel = await openPanel()

    expect(await within(panel).findByText('查過最近入庫')).toBeInTheDocument()
    expect(within(panel).getByText('這一版畫不出這個結果的卡片。')).toBeInTheDocument()
    expect(within(panel).queryByRole('region')).not.toBeInTheDocument()
    expect(within(panel).getByText('這週入庫了兩部。')).toBeInTheDocument()
  })

  it('存下的結果是舊的形狀時，那一張卡退回摘要，對話照常', async () => {
    // React 會把接住的錯誤印到 console；這一條就是要它丟。
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': { body: askedThisWeek('RecentImports', { since: AT }) },
      },
    })
    const panel = await openPanel()

    expect(await within(panel).findByText('這一版畫不出這個結果的卡片。')).toBeInTheDocument()
    expect(within(panel).getByText('這週入庫了兩部。')).toBeInTheDocument()
    quiet.mockRestore()
  })
})

describe('工具沒做成與保險絲', () => {
  it('清單外的工具說人話，到了輪數上限說出幾次', async () => {
    render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
        'GET /api/conversations/7': {
          body: conversation(7, [
            { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: '刪掉' }] },
            {
              id: 2,
              kind: 'model',
              created_at: AT,
              parts: [{ type: 'tool_call', id: 'c1', name: 'recent_imports', arguments: '{}' }],
            },
            {
              id: 3,
              kind: 'tools',
              created_at: AT,
              parts: [
                {
                  type: 'tool_result',
                  call_id: 'c1',
                  tool: 'recent_imports',
                  outcome: 'refused',
                  result_type: 'Refusal',
                  result: {
                    tool: 'recent_imports',
                    reason: 'unknown_tool',
                    detail: '',
                    next: 'give_up',
                  },
                },
              ],
            },
            {
              id: 4,
              kind: 'notice',
              created_at: AT,
              parts: [{ type: 'notice', notice: 'round_limit', limit: 10 }],
            },
          ]),
        },
      },
    })
    const panel = await openPanel()

    expect(await within(panel).findByText('最近入庫沒做成')).toBeInTheDocument()
    expect(within(panel).getByText('你的清單上沒有這個工具')).toBeInTheDocument()
    expect(within(panel).getByText(/到了 10 次的上限/)).toBeInTheDocument()
  })
})

describe('只能聊天', () => {
  it('標明這個模型只能聊天，輸入框照常', async () => {
    render({ status: { ready: true, chat_only: true, tools: [] } })

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

  it('收起再打開，打了還沒送出的字還在（面板收起只是藏起來，M5 票 15b）', async () => {
    render()
    const panel = await openPanel()
    await userEvent.type(within(panel).getByRole('textbox'), '還沒送出')

    await userEvent.click(within(panel).getByRole('button', { name: '關閉' }))
    const again = await openPanel()

    expect(within(again).getByRole('textbox')).toHaveValue('還沒送出')
    expect(within(again).getByRole('textbox')).toHaveFocus()
  })

  it('換頁時面板不重建：字還在，是同一個面板（M5 票 15b）', async () => {
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: ADMIN },
      'GET /api/assistant': { body: READY },
      'GET /api/conversations': { body: [] },
    })
    const { router } = renderApp('/health')
    const panel = await openPanel()
    await userEvent.type(within(panel).getByRole('textbox'), '還沒送出')

    await router.navigate({ to: '/jobs' })

    await waitFor(() => expect(router.state.location.pathname).toBe('/jobs'))
    expect(screen.getByRole('complementary', { name: '助理' })).toBe(panel)
    expect(within(panel).getByRole('textbox')).toHaveValue('還沒送出')
  })

  it('Esc 也關得掉', async () => {
    render()
    await openPanel()

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
  })
})

describe('窄版（`lg` 以下，面板取代頁面）', () => {
  /** 讓 `matchMedia` 說這是手機寬度：jsdom 沒有它，面板沒有它時當桌機。 */
  function narrow() {
    vi.stubGlobal(
      'matchMedia',
      (query: string) => ({ matches: false, media: query }) as unknown as MediaQueryList,
    )
  }

  it('面板裡的連結換了頁就收起面板，看得到那一頁', async () => {
    narrow()
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: ADMIN },
      'GET /api/assistant': { body: { ready: false, chat_only: false, tools: [] } },
      'GET /api/conversations': { body: [] },
    })
    const { router } = renderApp('/')
    const panel = await openPanel()

    await userEvent.click(await within(panel).findByRole('link', { name: '去設定' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/ai'))
    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
  })

  it('連到的就是這一頁（在活動頁按「活動」）也收起面板', async () => {
    narrow()
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: ADMIN },
      'GET /api/assistant': { body: READY },
      'GET /api/conversations': { body: [] },
      'GET /api/ai-activity': { body: { entries: [], truncated: false } },
    })
    renderApp('/ai-activity')
    const panel = await openPanel()

    await userEvent.click(within(panel).getByRole('link', { name: '活動' }))

    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
    expect(localStorage.getItem('berth.assistant.open')).toBe('0')
  })

  it('面板以外的換頁（瀏覽器的上一頁）也收起面板，看得到那一頁', async () => {
    narrow()
    stubApi({
      'GET /api/health': { body: HEALTHY },
      'GET /api/auth/me': { body: ADMIN },
      'GET /api/assistant': { body: READY },
      'GET /api/conversations': { body: [] },
    })
    const { router } = renderApp('/health')
    await openPanel()

    await router.navigate({ to: '/jobs' })

    await waitFor(() => expect(router.state.location.pathname).toBe('/jobs'))
    await waitFor(() =>
      expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument(),
    )
  })

  it('不記得上次開著：每次打開網頁看到的是那一頁', async () => {
    narrow()
    localStorage.setItem('berth.assistant.open', '1')
    render()

    expect(await screen.findByRole('button', { name: '助理' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(screen.queryByRole('complementary', { name: '助理' })).not.toBeInTheDocument()
  })
})

describe('確認卡', () => {
  const ADD_DMHY: ProposalCard = {
    id: 5,
    tool: 'add_indexer',
    cause: 'irreversible',
    reason: '你說要多一個動畫的索引站。',
    preview_type: 'IndexerAddition',
    preview: {
      site: 'dmhy',
      name: 'dmhy',
      url: 'https://share.dmhy.org/',
      description: 'dmhy is a TAIWANESE Public magnet tracker for ANIME',
      language: 'zh-TW',
      prowlarr: 'http://prowlarr:9696',
      origin: 'bundled',
    },
    status: 'proposed',
    result_type: null,
    result: null,
    created_at: AT,
    decided_at: null,
  }

  const DELETE_DUNE: ProposalCard = {
    ...ADD_DMHY,
    id: 6,
    tool: 'delete_downloads',
    reason: '你說這部不用再做種了。',
    preview_type: 'DownloadsDeletion',
    preview: {
      media: 'movie:693134',
      title: '沙丘：第二部',
      title_en: 'Dune: Part Two',
      jobs: [
        {
          hash: 'abc',
          name: '[Demo] Dune Part Two',
          state: 'imported',
          files: [
            '/data/torrent/complete/movies/Dune.Part.Two.mkv',
            '/data/torrent/complete/movies/Dune.nfo',
          ],
          missing: 0,
          bytes: 4_000_000_000,
          reclaimable: 0,
        },
      ],
    },
  }

  /** 叫 AI 做了一件不可逆的事、它停在一張卡上，存下來的那幾則。 */
  function proposed(card: ProposalCard, live: ProposalCard = card): Conversation {
    return {
      ...conversation(7, [
        { id: 1, kind: 'user', created_at: AT, parts: [{ type: 'user_text', text: '做吧' }] },
        {
          id: 2,
          kind: 'model',
          created_at: AT,
          parts: [{ type: 'tool_call', id: 'c1', name: card.tool, arguments: '{}' }],
        },
        {
          id: 3,
          kind: 'tools',
          created_at: AT,
          parts: [
            {
              type: 'tool_result',
              call_id: 'c1',
              tool: card.tool,
              outcome: 'proposed',
              result_type: 'ProposalCard',
              result: card,
            },
          ],
        },
      ]),
      proposals: [live],
    }
  }

  function saved(body: Conversation | (() => Conversation), routes: StubRoutes = {}) {
    return render({
      routes: {
        'GET /api/conversations': { body: [{ id: 7, title: '做吧', updated_at: AT }] },
        'GET /api/conversations/7': () => ({ body: typeof body === 'function' ? body() : body }),
        ...routes,
      },
    })
  }

  it('說出會發生什麼與 AI 的理由，按確認之後說後端真的做了什麼', async () => {
    let confirmed = false
    const done: ProposalCard = {
      ...ADD_DMHY,
      status: 'confirmed',
      result_type: 'IndexerAdded',
      result: { site: 'dmhy', name: 'dmhy' },
    }
    const stub = saved(() => proposed(ADD_DMHY, confirmed ? done : ADD_DMHY), {
      'POST /api/proposals/5/confirm': () => {
        confirmed = true
        return { body: done }
      },
    })
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '加索引站' })
    expect(within(panel).getByText('提出了加索引站')).toBeInTheDocument()
    expect(within(card).getByText('等你確認')).toBeInTheDocument()
    expect(within(card).getByText(/把 dmhy 加進 Prowlarr/)).toBeInTheDocument()
    expect(within(card).getByText('https://share.dmhy.org/')).toBeInTheDocument()
    expect(within(card).getByText('你說要多一個動畫的索引站。')).toBeInTheDocument()

    await userEvent.click(within(card).getByRole('button', { name: '確認加入' }))

    expect(await within(card).findByText('已加入 dmhy。')).toBeInTheDocument()
    expect(within(card).getByText('已確認')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: '確認加入' })).not.toBeInTheDocument()
    expect(stub.mock.calls.filter(([url]) => url === '/api/proposals/5/confirm')).toHaveLength(1)
    // 兩顆鍵消失了：焦點落在說結果的那一格，不掉到頁面頂端（M5 票 15）。
    await waitFor(() => expect(within(card).getByRole('status')).toHaveFocus())
  })

  it('刪下載的卡列出每一個要刪的檔案，空不出空間時照實說', async () => {
    saved(proposed(DELETE_DUNE))
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '刪下載' })
    const files = within(card).getByRole('list', { name: '[Demo] Dune Part Two 會刪的檔案' })
    expect(
      within(files)
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual([
      '/data/torrent/complete/movies/Dune.Part.Two.mkv',
      '/data/torrent/complete/movies/Dune.nfo',
    ])
    expect(within(card).getByText(/媒體庫的鏈接留著/)).toBeInTheDocument()
    expect(within(card).getByText('媒體庫還留著同一份：刪了不會空出空間。')).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: '確認刪除' })).toBeInTheDocument()
  })

  it('按下去的時候已經不成立，卡上說為什麼', async () => {
    const lapsed: ProposalCard = {
      ...ADD_DMHY,
      status: 'expired',
      result_type: 'Refusal',
      result: { tool: 'add_indexer', reason: 'site_present', detail: 'dmhy', next: 'give_up' },
    }
    saved(proposed(ADD_DMHY, lapsed))
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '加索引站' })
    expect(within(card).getByText('失效')).toBeInTheDocument()
    expect(
      within(card).getByText(/按下去的時候已經不成立.*這一站已經在 Prowlarr 裡了。/),
    ).toBeInTheDocument()
  })

  it('拒絕了就說什麼都沒做', async () => {
    saved(proposed(ADD_DMHY, { ...ADD_DMHY, status: 'rejected' }))
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '加索引站' })
    expect(within(card).getByText('拒絕了，什麼都沒做。')).toBeInTheDocument()
  })

  it('回覆還在跑時按不得', async () => {
    saved({ ...proposed(ADD_DMHY), replying: true })
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '加索引站' })
    expect(within(card).getByRole('button', { name: '確認加入' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    expect(within(card).getByText('回覆講完才按得到。')).toBeInTheDocument()
  })

  it('別人先按了就地說，不當成做好了', async () => {
    saved(proposed(ADD_DMHY), {
      'POST /api/proposals/5/reject': {
        status: 409,
        body: { detail: { reason: 'already_decided', detail: '5' } },
      },
    })
    const panel = await openPanel()

    const card = await within(panel).findByRole('region', { name: '加索引站' })
    await userEvent.click(within(card).getByRole('button', { name: '拒絕' }))

    expect(await within(card).findByText('這張卡已經有人按過了。')).toBeInTheDocument()
    // 鍵還在（卡照舊等人按）：焦點留在按下去的那一顆上。
    expect(within(card).getByRole('button', { name: '拒絕' })).toHaveFocus()
  })
})

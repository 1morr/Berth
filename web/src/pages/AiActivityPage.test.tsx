import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiActivity, AiActivityEntry } from '../api/aiActivity'
import type { AssistantStatus } from '../api/assistant'
import { HEALTHY, REQUEST_FAILURES, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

/**
 * AI 活動頁（M5 票 14）：一列一筆，說得出何時、代誰、做了什麼、為什麼；撤得了就地撤，撤不了說為什麼。
 * 斷言畫面上讀得到的字；後端的資料形狀由 `tests/integration/test_ai_activity*.py` 守。
 */

const AT = '2026-10-24T12:00:00Z'
const UNDO = 'POST /api/conversations/7/messages/3/tools/c0/undo'

const READY: AssistantStatus = { ready: true, chat_only: false, tools: [] }

function entry(overrides: Partial<AiActivityEntry> = {}): AiActivityEntry {
  return {
    conversation_id: 7,
    conversation_title: '幫我找孤獨搖滾',
    own: true,
    message_id: 3,
    call_id: 'c0',
    at: AT,
    user_id: 1,
    user_name: 'skipper',
    via: 'ai',
    tool: 'submit_search_result',
    arguments: { release_id: 'r1', route_id: 2, episodes: [1, 2] },
    reason: '這一筆是最新的 1080p 繁中',
    result_type: 'SubmittedJob',
    result: { hash: 'abc', name: '[ANi] 孤獨搖滾 - 01', media: 'tv:1', created: true },
    tokens: { input: 1200, output: 345 },
    undo: 'undoable',
    undone_at: null,
    ...overrides,
  }
}

function render(
  entries: AiActivityEntry[],
  { role = 'admin', ready = true, routes = {} as StubRoutes, truncated = false } = {},
) {
  const activity: AiActivity = { entries, truncated }
  const stub = stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role } },
    'GET /api/assistant': ready ? { body: READY } : { status: 404, body: {} },
    'GET /api/ai-activity': { body: activity },
    'GET /api/conversations': { body: [] },
    ...routes,
  })
  renderApp('/ai-activity')
  return stub
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AI 活動頁的列', () => {
  it('說動作、對象、代誰、出自哪則對話、tokens 與理由', async () => {
    render([entry()])

    const row = await screen.findByRole('article', { name: '[ANi] 孤獨搖滾 - 01' })
    expect(within(row).getByText('送單')).toBeInTheDocument()
    expect(within(row).getByText('AI 代 skipper 做的')).toBeInTheDocument()
    expect(within(row).getByText('出自對話「幫我找孤獨搖滾」')).toBeInTheDocument()
    expect(within(row).getByText('這次回覆 1,545 tokens')).toBeInTheDocument()
    expect(within(row).getByText('AI 的理由')).toBeInTheDocument()
    expect(within(row).getByText('這一筆是最新的 1080p 繁中')).toBeInTheDocument()
  })

  it('訂閱的對象是 Feed 名；人確認的說「確認的」；tokens 不知道時印「—」；沒有理由就沒有那一格', async () => {
    render([
      entry({
        tool: 'subscribe_mikan',
        via: 'confirmed',
        user_name: 'deckhand',
        reason: '',
        tokens: { input: null, output: null },
        arguments: {},
        result_type: 'Subscribed',
        result: { feed: { name: 'Mikan 孤獨搖滾' } },
      }),
    ])

    const row = await screen.findByRole('article', { name: 'Mikan 孤獨搖滾' })
    expect(within(row).getByText('訂閱')).toBeInTheDocument()
    expect(within(row).getByText('deckhand 確認的')).toBeInTheDocument()
    expect(within(row).getByText('這次回覆 — tokens')).toBeInTheDocument()
    expect(within(row).queryByText('AI 的理由')).toBeNull()
    expect(within(row).queryByText('輸入')).toBeNull()
  })

  it('只知道一格 tokens 時也印「—」，不印一個少算的數', async () => {
    render([entry({ tokens: { input: 1200, output: null } })])

    const row = await screen.findByRole('article', { name: '[ANi] 孤獨搖滾 - 01' })
    expect(within(row).getByText('這次回覆 — tokens')).toBeInTheDocument()
  })

  it('加索引站的對象是站名', async () => {
    render([entry({ tool: 'add_indexer', result_type: 'IndexerAdded', result: { name: 'dmhy' } })])

    expect(await screen.findByRole('article', { name: 'dmhy' })).toBeInTheDocument()
  })

  it('沒有對象的型別不印對象，列仍有名字', async () => {
    render([
      entry({ tool: 'delete_downloads', result_type: 'DownloadsDeleted', result: { jobs: [] } }),
    ])

    expect(await screen.findByRole('article', { name: '刪下載' })).toBeInTheDocument()
  })

  it('展開之後每個輸入欄一條，非字串的值以 JSON 印出', async () => {
    render([entry()])
    const row = await screen.findByRole('article', { name: '[ANi] 孤獨搖滾 - 01' })

    // 摘要用字說它展得開（The Summary Is One Button Rule，M5 票 15）。
    const summary = within(row).getByText('輸入').closest('summary') as HTMLElement
    expect(within(summary).getByText('展開')).toBeInTheDocument()
    await userEvent.click(summary)

    expect(within(row).getByText('release_id')).toBeInTheDocument()
    expect(within(row).getByText('r1')).toBeInTheDocument()
    expect(within(row).getByText('[1,2]')).toBeInTheDocument()
  })

  it('en：tokens 的千分位與句子跟著語言', async () => {
    render([entry()])
    await screen.findByRole('article', { name: '[ANi] 孤獨搖滾 - 01' })

    await userEvent.click(screen.getByRole('button', { name: 'EN' }))

    expect(await screen.findByText('1,545 tokens in this reply')).toBeInTheDocument()
    expect(screen.getByText('Done by the AI for skipper')).toBeInTheDocument()
  })
})

describe('撤銷那一格', () => {
  it('撤不了的說為什麼；撤過的說已撤銷', async () => {
    render([
      entry({ call_id: 'a', undo: 'no_inverse', tool: 'add_indexer', result_type: 'IndexerAdded' }),
      entry({ call_id: 'b', undo: 'not_allowed' }),
      entry({ call_id: 'c', undo: 'undone', undone_at: AT }),
      entry({ call_id: 'd', undo: 'nothing_done' }),
    ])

    expect(await screen.findByText('這一件做了就撤不回。')).toBeInTheDocument()
    expect(screen.getByText('只有管理員撤得了這一筆。')).toBeInTheDocument()
    expect(screen.getByText(/這一次什麼都沒改/)).toBeInTheDocument()
    expect(screen.getByText(/已撤銷/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '撤銷送單' })).toBeNull()
  })

  it('撤得了的：按撤銷、確認，打撤銷端點並重問清單，列留著說已撤銷', async () => {
    let undone = false
    const stub = render([], {
      routes: {
        'GET /api/ai-activity': () => ({
          body: {
            entries: [
              entry({ undo: undone ? 'undone' : 'undoable', undone_at: undone ? AT : null }),
            ],
            truncated: false,
          } satisfies AiActivity,
        }),
        [UNDO]: () => {
          undone = true
          return {
            body: {
              type: 'undone',
              message_id: 3,
              call_id: 'c0',
              tool: 'submit_search_result',
              result_type: 'Unsubscribed',
              result: {},
            },
          }
        },
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: '撤銷送單' }))
    expect(screen.getByText(/從 qBittorrent 移除這個 torrent/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: '撤銷送單' }).at(-1) as HTMLElement)

    expect(await screen.findByText(/已撤銷/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '撤銷送單' })).toBeNull()
    expect(stub.mock.calls.some(([url]) => String(url).endsWith('/tools/c0/undo'))).toBe(true)
    expect(stub.mock.calls.filter(([url]) => String(url) === '/api/ai-activity')).toHaveLength(2)
  })

  it('撤銷被拒時說原因，鍵還在', async () => {
    render([entry()], {
      routes: {
        [UNDO]: {
          body: {
            type: 'undone',
            call_id: 'c0',
            tool: 'submit_search_result',
            result_type: 'Refusal',
            result: { reason: 'client_unreachable', detail: '' },
          },
        },
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: '撤銷送單' }))
    await userEvent.click(screen.getAllByRole('button', { name: '撤銷送單' }).at(-1) as HTMLElement)

    expect(await screen.findByRole('alert')).toHaveTextContent('撤銷沒做成')
    expect(screen.getAllByRole('button', { name: '撤銷送單' }).length).toBeGreaterThan(0)
  })
})

describe('出自哪則對話', () => {
  it('自己的對話是按鈕，按了打開側面板；別人的只印標題', async () => {
    render(
      [
        entry({ call_id: 'mine' }),
        entry({
          call_id: 'theirs',
          own: false,
          conversation_id: 9,
          conversation_title: '別人的對話',
        }),
      ],
      {
        routes: {
          'GET /api/conversations/7': {
            body: {
              id: 7,
              title: '幫我找孤獨搖滾',
              replying: false,
              messages: [],
              proposals: [],
            },
          },
        },
      },
    )

    const button = await screen.findByRole('button', { name: '出自對話「幫我找孤獨搖滾」' })
    expect(screen.getByText('出自對話「別人的對話」').tagName).toBe('SPAN')
    expect(screen.queryByRole('button', { name: '出自對話「別人的對話」' })).toBeNull()

    await userEvent.click(button)

    expect(await screen.findByRole('complementary', { name: '助理' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveFocus())
  })
})

describe('空狀態與讀取', () => {
  it('一般使用者與管理員各一種說法', async () => {
    render([], { role: 'user' })
    expect(await screen.findByText(/AI 還沒替你做過事。/)).toBeInTheDocument()
    expect(screen.getByText(/在側面板叫助理送單或訂閱/)).toBeInTheDocument()
  })

  it('管理員：還沒替任何人做過事，導言說是所有人的', async () => {
    render([])
    expect(await screen.findByText(/AI 還沒替任何人做過事。/)).toBeInTheDocument()
    expect(screen.getByText(/（所有人的）/)).toBeInTheDocument()
  })

  it('超過一次列的筆數時說更早的不列', async () => {
    render([entry()], { truncated: true })
    expect(await screen.findByText('更早的不列在這裡。')).toBeInTheDocument()
  })

  it.each(REQUEST_FAILURES)('讀不到（%s）：說讀不到', async (_name, failure) => {
    render([], { routes: { 'GET /api/ai-activity': failure } })
    expect(await screen.findByText(/讀不到 AI 活動/)).toBeInTheDocument()
  })
})

describe('導覽', () => {
  it('AI 設定好時有這一格，一般使用者也有', async () => {
    render([], { role: 'user' })
    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))
    expect(await nav.findByRole('link', { name: 'AI 活動' })).toHaveAttribute(
      'href',
      '/ai-activity',
    )
  })

  it('AI 沒設定好時沒有這一格，網址照樣進得來', async () => {
    render([entry()], { ready: false })
    await screen.findByRole('article', { name: '[ANi] 孤獨搖滾 - 01' })
    const nav = within(screen.getByRole('navigation', { name: '主要導覽' }))
    expect(nav.queryByRole('link', { name: 'AI 活動' })).toBeNull()
  })
})

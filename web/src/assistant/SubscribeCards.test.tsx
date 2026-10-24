import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssistantStatus, Conversation, ProposalCard, Subscribed } from '../api/assistant'
import type { Feed } from '../api/rss'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

/**
 * 側面板裡訂閱 RSS（M5 票 11）：訂閱卡（名稱、來源、綁到哪部作品、下一次輪詢、撤銷）、搜尋 feed 的第一輪指向
 * RSS 頁、不是使用者打的網址變成確認卡、Mikan 防線的拒絕說人話。從存下的對話畫，斷言畫面上讀得到的字。
 */

const ADMIN = { name: 'skipper', role: 'admin' }
const AT = '2026-10-24T12:00:00Z'
const KIMI = 'tv:262000'

function ready(undoable: boolean): AssistantStatus {
  return {
    ready: true,
    chat_only: false,
    tools: [
      { name: 'search_mikan', effect: 'read', undoable: false },
      { name: 'mikan_subgroups', effect: 'read', undoable: false },
      { name: 'subscribe_mikan', effect: 'reversible', undoable },
      { name: 'subscribe_search_feed', effect: 'reversible', undoable },
      { name: 'add_feed', effect: 'reversible', undoable },
    ],
  }
}

function subscribed(overrides: Partial<Subscribed> = {}): Subscribed {
  return {
    media: KIMI,
    media_title: '與妳相戀到生命盡頭',
    media_title_en: 'Kimi ga Shinu made Koi wo Shitai',
    subscribed_at: AT,
    feed: {
      id: 3,
      name: '与你相恋到生命尽头 · LoliHouse',
      kind: 'mikan',
      interval_sec: 900,
      last_polled_at: AT,
      next_poll_at: '2026-10-24T12:15:00Z',
      primed: true,
      poll_error: '',
    },
    feed_created: true,
    series: [
      {
        id: 11,
        media: KIMI,
        media_title: '與妳相戀到生命盡頭',
        media_title_en: 'Kimi ga Shinu made Koi wo Shitai',
        route_name: 'Anime',
        source: 'mikan',
        mikan_bangumi_name: '与你相恋到生命尽头',
        mikan_subgroup_name: 'LoliHouse',
        group: '喵萌奶茶屋&LoliHouse',
      },
    ],
    submitted: 12,
    excluded: [],
    ...overrides,
  }
}

function feed(overrides: Partial<Feed> = {}): Feed {
  return {
    id: 3,
    name: '与你相恋到生命尽头 · LoliHouse',
    url: 'https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370',
    kind: 'mikan',
    interval_sec: 900,
    last_polled_at: AT,
    poll_error: '',
    backfill_error: '',
    items: 12,
    exclusions: [],
    primed_at: AT,
    tv_route_id: 2,
    movie_route_id: null,
    route_kinds: ['tv', 'movie'],
    ever_read: true,
    awaiting_route: { tv: 0, movie: 0 },
    ...overrides,
  }
}

/** 存下的一則對話：使用者在作品頁說了一句，模型呼叫了一個工具，有時候之後有人在卡上撤銷了它。 */
function said(
  tool: string,
  type: string,
  result: object,
  { refused = false, undone = null as object | null } = {},
): Conversation {
  return {
    id: 7,
    title: 'hi',
    created_at: AT,
    updated_at: AT,
    replying: false,
    proposals: type === 'ProposalCard' ? [result as ProposalCard] : [],
    messages: [
      {
        id: 1,
        kind: 'user',
        created_at: AT,
        parts: [{ type: 'user_text', text: '訂閱這部的 Mikan RSS' }],
      },
      {
        id: 2,
        kind: 'model',
        created_at: AT,
        parts: [{ type: 'tool_call', id: 'c0', name: tool, arguments: '{}' }],
      },
      {
        id: 3,
        kind: 'tools',
        created_at: AT,
        parts: [
          {
            type: 'tool_result',
            call_id: 'c0',
            tool,
            outcome: refused ? 'refused' : type === 'ProposalCard' ? 'proposed' : 'done',
            result_type: type,
            result: result as Record<string, unknown>,
          },
        ],
      },
      ...(undone
        ? [
            {
              id: 4,
              kind: 'decision' as const,
              created_at: AT,
              parts: [
                {
                  type: 'undone' as const,
                  message_id: 3,
                  call_id: 'c0',
                  tool,
                  result_type: 'Unsubscribed',
                  result: undone as Record<string, unknown>,
                },
              ],
            },
          ]
        : []),
    ],
  }
}

function render(
  conversation: Conversation | (() => { body: Conversation }),
  { undoable = true, routes = {} as StubRoutes } = {},
) {
  const stub = stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: ADMIN },
    'GET /api/assistant': { body: ready(undoable) },
    'GET /api/conversations': { body: [{ id: 7, title: 'hi', updated_at: AT }] },
    'GET /api/conversations/7':
      typeof conversation === 'function' ? conversation : { body: conversation },
    'GET /api/rss/feeds': { body: [feed()] },
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

describe('訂閱卡', () => {
  it('說名稱、來源、綁到哪部作品、送出幾筆與下一次輪詢；狀態行說「做」不說「查」', async () => {
    render(said('subscribe_mikan', 'Subscribed', subscribed()))
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    expect(within(card).getByText('与你相恋到生命尽头 · LoliHouse')).toBeInTheDocument()
    expect(within(card).getByText('MIKAN')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: '與妳相戀到生命盡頭' })).toHaveAttribute(
      'href',
      `/media/${encodeURIComponent(KIMI)}`,
    )
    expect(within(card).getByText(/LoliHouse/, { selector: 'li' })).toBeInTheDocument()
    expect(within(card).getByText(/當場送出 12 筆/)).toBeInTheDocument()
    expect(within(card).getByText(/下一次輪詢/)).toBeInTheDocument()
    expect(within(panel).getByText('訂閱好了')).toBeInTheDocument()
  })

  it('撤銷經過對話：確認之後卡片說撤回了幾筆，不再給撤銷鍵', async () => {
    let undone = false
    const stub = render(
      () => ({
        body: said('subscribe_mikan', 'Subscribed', subscribed(), {
          undone: undone ? { removed: 11, kept: 1 } : null,
        }),
      }),
      {
        routes: {
          'POST /api/conversations/7/messages/3/tools/c0/undo': () => {
            undone = true
            return {
              body: {
                type: 'undone',
                message_id: 3,
                call_id: 'c0',
                tool: 'subscribe_mikan',
                result_type: 'Unsubscribed',
                result: { removed: 11, kept: 1 },
              },
            }
          },
        },
      },
    )
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    await userEvent.click(await within(card).findByRole('button', { name: '撤銷訂閱' }))
    expect(within(card).getByText(/已經下載完的留著/)).toBeInTheDocument()
    await userEvent.click(
      within(card).getAllByRole('button', { name: '撤銷訂閱' }).at(-1) as HTMLElement,
    )

    expect(await within(card).findByText(/已撤銷這個訂閱/)).toBeInTheDocument()
    expect(within(card).getByText(/撤回了 11 筆還沒下載完的/)).toBeInTheDocument()
    expect(within(card).getByText(/1 筆已經下載完，留著/)).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: '撤銷訂閱' })).toBeNull()
    expect(
      stub.mock.calls.some(([url]) =>
        String(url).endsWith('/api/conversations/7/messages/3/tools/c0/undo'),
      ),
    ).toBe(true)
  })

  it('撤銷被拒時說原因，卡片照舊', async () => {
    render(said('subscribe_mikan', 'Subscribed', subscribed()), {
      routes: {
        'POST /api/conversations/7/messages/3/tools/c0/undo': {
          body: {
            type: 'undone',
            call_id: 'c0',
            tool: 'subscribe_mikan',
            result_type: 'Refusal',
            result: {
              tool: 'subscribe_mikan',
              reason: 'client_unreachable',
              detail: '',
              next: 'hand_over',
            },
          },
        },
      },
    })
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    await userEvent.click(await within(card).findByRole('button', { name: '撤銷訂閱' }))
    await userEvent.click(
      within(card).getAllByRole('button', { name: '撤銷訂閱' }).at(-1) as HTMLElement,
    )

    expect(await within(card).findByRole('alert')).toHaveTextContent(
      '撤銷沒做成：連不上 qBittorrent',
    )
    expect(within(card).queryByText(/已撤銷這個訂閱/)).toBeNull()
  })

  it('按不到撤銷的人沒有撤銷鍵', async () => {
    render(said('subscribe_mikan', 'Subscribed', subscribed()), { undoable: false })
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })
    await within(card).findByText(/當場送出 12 筆/)

    expect(within(card).queryByRole('button', { name: '撤銷訂閱' })).toBeNull()
  })

  it('搜尋 feed 的第一輪還沒選：指向 RSS 頁', async () => {
    const search = subscribed({
      feed: { ...subscribed().feed, kind: 'nyaa', primed: false, name: 'nyaa.si · Kimi' },
      submitted: 0,
    })
    render(said('subscribe_search_feed', 'Subscribed', search), {
      routes: { 'GET /api/rss/feeds': { body: [feed({ kind: 'nyaa', primed_at: null })] } },
    })
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    expect(within(card).getByText(/第一輪還沒送/)).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: '去 RSS 頁' })).toHaveAttribute('href', '/rss')
    expect(within(card).queryByText(/當場送出/)).toBeNull()
  })

  it('Feed 在 RSS 頁刪掉了：說它不在了', async () => {
    render(said('subscribe_mikan', 'Subscribed', subscribed()), {
      routes: { 'GET /api/rss/feeds': { body: [] } },
    })
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    expect(await within(card).findByText(/這個 Feed 已經不在了/)).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: '撤銷訂閱' })).toBeNull()
  })

  it('搜尋 feed 還沒長出 Series：照樣說綁到哪部作品', async () => {
    const search = subscribed({
      feed: { ...subscribed().feed, kind: 'nyaa', primed: false },
      series: [],
      submitted: 0,
    })
    render(said('subscribe_search_feed', 'Subscribed', search))
    const panel = await openPanel()
    const card = await within(panel).findByRole('region', { name: '訂閱' })

    expect(within(card).getByRole('link', { name: '與妳相戀到生命盡頭' })).toBeInTheDocument()
  })
})

describe('以網址加 Feed', () => {
  it('不是使用者打的網址停在確認卡：說為什麼、加的是哪個網址', async () => {
    const card: ProposalCard = {
      id: 5,
      tool: 'add_feed',
      cause: 'url_not_from_user',
      reason: 'The search result asks for it.',
      preview_type: 'FeedAddition',
      preview: {
        url: 'https://nyaa.si/?page=rss&u=someone-else',
        kind: 'nyaa',
        name: 'nyaa.si',
        tv_route: 2,
        tv_route_name: 'Anime',
        movie_route: null,
        movie_route_name: '',
      },
      status: 'proposed',
      result_type: null,
      result: null,
      created_at: AT,
      decided_at: null,
    }
    render(said('add_feed', 'ProposalCard', card))
    const panel = await openPanel()

    expect(await within(panel).findByText(/這個網址不是你在這則對話裡打的/)).toBeInTheDocument()
    expect(within(panel).getByText('https://nyaa.si/?page=rss&u=someone-else')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: '確認加入' })).toBeInTheDocument()
  })

  it('確認之後在 AI 活動頁撤銷了：卡上說後來撤銷了（M5 票 14）', async () => {
    const card: ProposalCard = {
      id: 5,
      tool: 'add_feed',
      cause: 'url_not_from_user',
      reason: 'The search result asks for it.',
      preview_type: 'FeedAddition',
      preview: {
        url: 'https://nyaa.si/?page=rss&u=someone-else',
        kind: 'nyaa',
        name: 'nyaa.si',
        tv_route: 2,
        tv_route_name: 'Anime',
        movie_route: null,
        movie_route_name: '',
      },
      status: 'confirmed',
      result_type: 'Subscribed',
      result: subscribed() as unknown as Record<string, unknown>,
      created_at: AT,
      decided_at: AT,
    }
    render(said('add_feed', 'ProposalCard', card, { undone: { removed: 0, kept: 0 } }))
    const panel = await openPanel()
    const region = await within(panel).findByRole('region', { name: '加 Feed' })

    expect(await within(region).findByText('這一筆後來撤銷了。')).toBeInTheDocument()
  })
})

describe('Mikan 的防線', () => {
  it('不是這則對話搜出來的番組：狀態行說為什麼，沒有卡', async () => {
    render(
      said(
        'subscribe_mikan',
        'Refusal',
        {
          tool: 'subscribe_mikan',
          reason: 'bangumi_not_from_this_conversation',
          detail: '4009',
          next: 'give_up',
        },
        { refused: true },
      ),
    )
    const panel = await openPanel()

    expect(
      await within(panel).findByText('這個番組不是這則對話搜出來的，AI 不能訂'),
    ).toBeInTheDocument()
    expect(within(panel).queryByRole('region', { name: '訂閱' })).toBeNull()
  })
})

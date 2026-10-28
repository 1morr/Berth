import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AgentStatus } from '../api/agent'
import type { Proposal } from '../api/proposals'
import { renderInRoute } from '../test/render'
import { AgentPanel } from './AgentPanel'
import { AgentProvider } from './AgentProvider'

/**
 * 確認卡（M5 票 13）：卡片照伺服器的 Proposal 畫在那一格工具呼叫上；總覽卡逐列可勾、按下去逐列看得到
 * 結果；還在最後一則訊息裡的卡，按完才送恢復的那一則（前端的核准只是觸發），脫離過的不送。
 */

const CONVERSATION = 'c-test'
const CALL = 'card-1'
const TOOL = 'downloading_add_manual_download'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

function stream(chunks: object[]) {
  const body = [...chunks, 'DONE']
    .map((chunk) => `data: ${chunk === 'DONE' ? '[DONE]' : JSON.stringify(chunk)}\n\n`)
    .join('')
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' },
  })
}

function row(episode: number) {
  return {
    source: { title: `[ANi] SPY×FAMILY - ${episode}`, size: 734003200 },
    media_id: 'tv:120089',
    route_id: 3,
  }
}

function card(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: 7,
    command: 'downloading.add_manual_download',
    arguments: [row(1), row(2), row(3)],
    arguments_hash: 'h',
    preview: {
      effect: 'reversible',
      flags: ['downloads'],
      checked: [true, true, true],
      external_fields: [[], [], []],
      held_back: 0,
      torrents: [1, 1, 1],
      routes: [],
      subgroups: [],
      existing: [],
    },
    user_id: 1,
    proposer: 'ai',
    conversation_id: CONVERSATION,
    tool_call_id: CALL,
    status: 'pending',
    created_at: '2026-10-28T10:00:00Z',
    expires_at: '2026-10-29T10:00:00Z',
    decided_by: null,
    decided_at: null,
    selection: null,
    results: null,
    detached_at: null,
    routes: null,
    subgroups: null,
    ...overrides,
  }
}

function stored(state: 'approval-requested' | 'output-denied') {
  return [
    { id: 'u1', role: 'user', parts: [{ type: 'text', text: '下載第 1 到 3 集' }] },
    {
      id: 'a1',
      role: 'assistant',
      parts: [
        {
          type: `tool-${TOOL}`,
          toolCallId: CALL,
          state,
          input: { rows: [] },
          approval: { id: CALL },
        },
      ],
    },
  ]
}

let chats: Record<string, unknown>[] = []
let decisions: Record<string, unknown>[] = []

function serve(
  initial: Proposal,
  messages: unknown[],
  decided: (body: { approve: boolean }) => Proposal,
) {
  let current = initial
  chats = []
  decisions = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>(async (input, init) => {
      const method = init?.method ?? 'GET'
      const path = typeof input === 'string' ? input : String(input)
      if (path === '/api/auth/me') return json({ name: 'skipper', role: 'admin' })
      if (path === '/api/agent/status')
        return json({
          enabled: true,
          paused_until: null,
          pause_error: '',
          spend: null,
        } satisfies AgentStatus)
      if (path === `/api/agent/conversations/${CONVERSATION}`) {
        return json({ id: CONVERSATION, messages })
      }
      if (path.startsWith('/api/proposals?')) return json([current])
      if (method === 'POST' && path === `/api/proposals/${initial.id}/decide`) {
        const body = JSON.parse(String(init?.body)) as { approve: boolean }
        decisions.push(body)
        current = decided(body)
        return json(current)
      }
      if (path === '/api/routes') {
        return json([
          { route: { id: 3, name: 'Anime' }, usage: {} },
          { route: { id: 4, name: 'Movies' }, usage: {} },
        ])
      }
      if (path === '/api/rss/feeds') {
        return json([{ id: 9, name: 'acg.rip · Kimi · ANi', kind: 'acgrip', items: 5 }])
      }
      if (path === '/api/media/tv%3A120089') {
        return json({
          title: 'SPY×FAMILY',
          routes: [{ id: 3, name: 'Anime', slug: 'anime' }],
          folder_name: 'SPY x FAMILY (2022) [tmdbid-120089]',
          folder_frozen: false,
        })
      }
      if (method === 'POST' && path === '/api/agent/chat') {
        chats.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
        return stream([
          { type: 'start' },
          { type: 'start-step' },
          { type: 'tool-output-available', toolCallId: CALL, output: { executed: true } },
          { type: 'finish-step' },
          { type: 'start-step' },
          { type: 'text-start', id: 't1' },
          { type: 'text-delta', id: 't1', delta: '送出了第 2、3 集。' },
          { type: 'text-end', id: 't1' },
          { type: 'finish-step' },
          { type: 'finish' },
        ])
      }
      return json({ detail: 'Not Found' }, 404)
    }),
  )
}

const done = { outcome: 'done' as const, reason: '', detail: '', result: null }
const skipped = { outcome: 'skipped' as const, reason: '', detail: '', result: null }

function renderPanel() {
  return renderInRoute(
    <AgentProvider>
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

describe('ConfirmCard', () => {
  it('shows what will happen, sends only the ticked rows and then resumes the conversation', async () => {
    serve(card(), stored('approval-requested'), () =>
      card({ status: 'executed', selection: [1, 2], results: [skipped, done, done] }),
    )
    const user = userEvent.setup()
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    expect(within(section).getByText('要你確認')).toBeInTheDocument()
    expect(within(section).getByText('會送出 torrent')).toBeInTheDocument()
    expect(within(section).getByText('期限：')).toBeInTheDocument()
    await within(section).findAllByText('Anime')
    expect(within(section).getAllByText('SPY×FAMILY')).toHaveLength(3)
    expect(within(section).getAllByText('700 MB')).toHaveLength(3)

    await user.click(within(section).getByRole('checkbox', { name: '[ANi] SPY×FAMILY - 1' }))
    await user.click(within(section).getByRole('button', { name: '確認這 2 項' }))

    expect(decisions).toEqual([{ approve: true, selection: [1, 2] }])
    await waitFor(() => expect(within(section).getAllByText('完成')).toHaveLength(2))
    expect(within(section).getByText('沒勾，沒做')).toBeInTheDocument()
    expect(within(section).getByRole('status')).toHaveTextContent('做完了。')
    expect(within(section).queryByRole('button')).toBeNull()

    // 按完才送恢復的那一則：最後一則是助理的、那一格標成已回應。伺服器照 Proposal 決定，這只是觸發。
    await waitFor(() => expect(chats).toHaveLength(1))
    const [resume] = chats[0].messages as { role: string; parts: Record<string, unknown>[] }[]
    expect(resume.role).toBe('assistant')
    expect(resume.parts[0]).toMatchObject({
      toolCallId: CALL,
      state: 'approval-responded',
      approval: { id: CALL, approved: true },
    })
    expect(await screen.findByText('送出了第 2、3 集。')).toBeInTheDocument()
  })

  it('says once which folder the first send will fix for good, as the title page does', async () => {
    serve(card(), stored('approval-requested'), () => card({ status: 'rejected' }))
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })

    expect(await within(section).findAllByText('SPY x FAMILY (2022) [tmdbid-120089]')).toHaveLength(
      1,
    )
    expect(within(section).getByText(/送單成功那一刻這串字就定下來/)).toBeInTheDocument()
  })

  it('rejecting tells the conversation it was not approved', async () => {
    serve(card(), stored('approval-requested'), () => card({ status: 'rejected' }))
    const user = userEvent.setup()
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    await user.click(within(section).getByRole('button', { name: '拒絕' }))

    expect(decisions).toEqual([{ approve: false, selection: null }])
    await waitFor(() => expect(chats).toHaveLength(1))
    const [resume] = chats[0].messages as { parts: Record<string, unknown>[] }[]
    expect(resume.parts[0]).toMatchObject({ approval: { approved: false } })
    expect(within(section).getByRole('status')).toHaveTextContent('已拒絕，什麼都沒做。')
  })

  it('keeps the keyboard focus on the card once its buttons are gone', async () => {
    serve(card(), stored('approval-requested'), () => card({ status: 'rejected' }))
    const user = userEvent.setup()
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    within(section).getByRole('button', { name: '拒絕' }).focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(within(section).queryByRole('button')).toBeNull())
    expect(within(section).getByRole('heading', { name: '送出下載' })).toHaveFocus()
  })

  it('a detached card still runs when pressed, without resuming the conversation', async () => {
    serve(card({ status: 'detached', arguments: [row(1)] }), stored('output-denied'), () =>
      card({ status: 'executed', arguments: [row(1)], results: [done] }),
    )
    const user = userEvent.setup()
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    expect(within(section).getByText(/對話已經往下走了/)).toBeInTheDocument()
    // 單項卡：沒有勾選框，列出欄位。
    expect(within(section).queryByRole('checkbox')).toBeNull()
    await user.click(within(section).getByRole('button', { name: '確認' }))

    expect(decisions).toEqual([{ approve: true, selection: null }])
    await waitFor(() => expect(within(section).getByText('完成')).toBeInTheDocument())
    expect(chats).toEqual([])
  })

  it('with nothing ticked there is no confirm button, only a reason', async () => {
    serve(card({ arguments: [row(1), row(2)] }), stored('approval-requested'), () => card())
    const user = userEvent.setup()
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    for (const box of within(section).getAllByRole('checkbox')) await user.click(box)

    expect(within(section).queryByRole('button', { name: /確認/ })).toBeNull()
    expect(within(section).getByText('一列都沒勾。全部不要的話按「拒絕」。')).toBeInTheDocument()
  })

  it('marks only the fields copied from a web page, and says what is held for the next card', async () => {
    const feed = card({
      command: 'rss.add_feed',
      arguments: [
        {
          url: 'https://mikanani.me/RSS/MyBangumi?token=abc',
          name: 'Erai-raws',
          tv_route_id: 3,
          movie_route_id: 4,
          exclusions: [],
          interval_sec: 900,
        },
      ],
      preview: {
        effect: 'reversible',
        flags: ['connects_out', 'settings'],
        checked: [true],
        external_fields: [['name']],
        held_back: 0,
        torrents: [],
        routes: [],
        subgroups: [],
        existing: [],
      },
    })
    serve(feed, stored('approval-requested'), () => feed)
    renderPanel()

    const section = await screen.findByRole('region', { name: '新增 RSS Feed' })
    expect(within(section).getByText('會連到新位址')).toBeInTheDocument()
    expect(within(section).getByText(/從網頁或動漫資料站/)).toBeInTheDocument()
    expect(
      within(section).getByText('https://mikanani.me/RSS/MyBangumi?token=abc'),
    ).toBeInTheDocument()
    await within(section).findByText('Movies')
    // 名稱那一格是從網頁抄的：標記就在它旁邊，網址那一格沒有。
    const marks = within(section).getAllByText('出自外部來源')
    expect(marks).toHaveLength(1)
    expect(marks[0].closest('dd')).toHaveTextContent('Erai-raws')
  })

  it('a card with nothing from the web carries no warning; rows over the limit are announced', async () => {
    serve(
      card({
        preview: {
          effect: 'reversible',
          flags: ['downloads'],
          checked: [true, true, true],
          external_fields: [[], [], []],
          held_back: 2,
          torrents: [1, 1, 1],
          routes: [],
          subgroups: [],
          existing: [],
        },
      }),
      stored('approval-requested'),
      () => card(),
    )
    renderPanel()

    const section = await screen.findByRole('region', { name: '送出下載' })
    expect(within(section).queryByText(/出自外部來源/)).toBeNull()
    expect(
      within(section).getByText(/另外 2 項不在這張卡上：一張卡送出的 torrent 有上限/),
    ).toBeInTheDocument()
  })

  it('a refused RSS row says why in words', async () => {
    const mikan = card({
      command: 'rss.subscribe_mikan',
      arguments: [
        {
          bangumi_id: 3310,
          subgroup_id: 583,
          media_id: 'tv:120089',
          route_id: 3,
          name: '',
          subgroup_name: 'ANi',
        },
      ],
      preview: {
        effect: 'reversible',
        flags: ['downloads'],
        checked: [true],
        external_fields: [[]],
        held_back: 0,
        torrents: [12],
        routes: [],
        subgroups: [],
        existing: [],
      },
      status: 'failed',
      results: [{ outcome: 'refused', reason: 'series_bound', detail: 'tv:1', result: null }],
    })
    serve(mikan, stored('output-denied'), () => mikan)
    renderPanel()

    const section = await screen.findByRole('region', { name: '訂閱 Mikan 番組' })
    expect(within(section).getByText('ANi')).toBeInTheDocument()
    expect(within(section).getByText(/這個 RSS Series 已經綁好了/)).toBeInTheDocument()
  })

  it('a Mikan subscription says it sends the whole season, and how many when Berth could tell', async () => {
    const mikan = (torrents: (number | null)[]) =>
      card({
        command: 'rss.subscribe_mikan',
        arguments: [
          {
            bangumi_id: 3310,
            subgroup_id: 583,
            media_id: 'tv:120089',
            route_id: 3,
            name: '',
            subgroup_name: 'ANi',
          },
        ],
        preview: {
          effect: 'reversible',
          flags: ['downloads'],
          checked: [true],
          external_fields: [[]],
          held_back: 0,
          torrents,
          routes: [],
          subgroups: [],
          existing: [],
        },
      })
    serve(mikan([12]), stored('approval-requested'), () => mikan([12]))
    const { unmount } = renderPanel()

    const section = await screen.findByRole('region', { name: '訂閱 Mikan 番組' })
    expect(within(section).getByText(/會送出整季：12 個 torrent/)).toBeInTheDocument()
    unmount()

    serve(mikan([null]), stored('approval-requested'), () => mikan([null]))
    renderPanel()
    const unknown = await screen.findByRole('region', { name: '訂閱 Mikan 番組' })
    expect(within(unknown).getByText(/會送出整季.*數量要送出時才知道/)).toBeInTheDocument()
  })

  describe('a work that fits more than one route (ticket 23b)', () => {
    const ask = (preselected: number | null) => ({
      options: [
        { id: 3, name: 'Anime' },
        { id: 5, name: 'TV' },
      ],
      preselected,
    })
    const asking = (
      rows: number,
      preselected: number | null = null,
      more: Partial<Proposal> = {},
    ) =>
      card({
        arguments: [row(1), row(2), row(3)].slice(0, rows),
        preview: {
          effect: 'reversible',
          flags: ['downloads'],
          checked: Array.from({ length: rows }, () => true),
          external_fields: Array.from({ length: rows }, () => []),
          held_back: 0,
          torrents: Array.from({ length: rows }, () => 1),
          routes: Array.from({ length: rows }, () => ask(preselected)),
          subgroups: [],
          existing: [],
        },
        ...more,
      })

    it('asks for one with nothing preselected and draws no confirm button until it is chosen', async () => {
      serve(asking(1), stored('approval-requested'), () =>
        asking(1, null, { status: 'executed', results: [done], routes: [5] }),
      )
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '送出下載' })
      const picker = within(section).getByRole('combobox', { name: 'Route' })
      expect(picker).toHaveValue('')
      expect(within(section).queryByRole('button', { name: '確認' })).toBeNull()
      expect(within(section).getByText('還有 1 列沒選 Route。')).toBeInTheDocument()

      await user.selectOptions(picker, 'TV')
      await user.click(within(section).getByRole('button', { name: '確認' }))

      expect(decisions).toEqual([{ approve: true, selection: null, routes: [5] }])
      // 做完之後那一格寫的是卡片上選的那一條，不是模型給的 Anime。
      await waitFor(() => expect(within(section).getByText('完成')).toBeInTheDocument())
      expect(within(section).queryByRole('combobox')).toBeNull()
      expect(within(section).getByText('TV')).toBeInTheDocument()
    })

    it('preselects the route this work used last, which can still be changed', async () => {
      serve(asking(1, 5), stored('approval-requested'), () => asking(1, 5))
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '送出下載' })
      const picker = within(section).getByRole('combobox', { name: 'Route' })
      expect(picker).toHaveValue('5')

      await user.selectOptions(picker, 'Anime')
      await user.click(within(section).getByRole('button', { name: '確認' }))

      expect(decisions).toEqual([{ approve: true, selection: null, routes: [3] }])
    })

    it('only the ticked rows need a route', async () => {
      serve(asking(2), stored('approval-requested'), () => asking(2))
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '送出下載' })
      const [first, second] = within(section).getAllByRole('combobox', { name: 'Route' })
      expect(within(section).getByText('還有 2 列沒選 Route。')).toBeInTheDocument()

      await user.selectOptions(second, 'TV')
      expect(within(section).getByText('還有 1 列沒選 Route。')).toBeInTheDocument()
      await user.click(within(section).getByRole('checkbox', { name: '[ANi] SPY×FAMILY - 1' }))
      // 沒勾的那一列不必選：下拉留著（勾回來時不跳版面），送出時那一格是 null。
      expect(first).toHaveValue('')
      await user.click(within(section).getByRole('button', { name: '確認這 1 項' }))

      expect(decisions).toEqual([{ approve: true, selection: [1], routes: [null, 5] }])
    })

    it('a work with a single route shows it as text, with no dropdown', async () => {
      serve(card({ arguments: [row(1)] }), stored('approval-requested'), () => card())
      renderPanel()

      const section = await screen.findByRole('region', { name: '送出下載' })
      await within(section).findByText('Anime')
      expect(within(section).queryByRole('combobox')).toBeNull()
      expect(within(section).getByRole('button', { name: '確認' })).toBeInTheDocument()
    })
  })

  describe('the subgroup is the user’s to choose (ticket 26)', () => {
    const option = (key: string, name: string, titles: string[]) => ({
      key,
      name,
      releases: titles.length,
      updated: '2026-10-20',
      latest: titles[0] ?? '',
      titles,
    })
    const ANI = option('ANi', 'ANi', ['[ANi] Kimi - 02 [1080P]', '[ANi] Kimi - 01 [1080P]'])
    const MOUSE = option('黒ネズミたち', '黒ネズミたち', ['[黒ネズミたち] Kimi - 02 (CR)'])
    const keyword = (preselected: string | null, more: Partial<Proposal> = {}) =>
      card({
        command: 'rss.subscribe_search',
        arguments: [
          {
            kind: 'acgrip',
            term: 'Kimi ga Shinu made Koi wo Shitai',
            subgroup: 'ANi',
            media_id: 'tv:120089',
            route_id: 3,
          },
        ],
        preview: {
          effect: 'reversible',
          flags: ['downloads'],
          checked: [true],
          external_fields: [[]],
          held_back: 0,
          torrents: [2],
          routes: [],
          subgroups: [{ options: [ANI, MOUSE], preselected, required: true }],
          existing: [],
        },
        ...more,
      })

    it('draws no confirm button until a subgroup is chosen, then sends the one chosen', async () => {
      serve(keyword(null), stored('approval-requested'), () =>
        keyword(null, { status: 'executed', results: [done], subgroups: ['黒ネズミたち'] }),
      )
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '訂閱關鍵字搜尋' })
      expect(within(section).queryByRole('button', { name: '確認' })).toBeNull()
      expect(within(section).getByText('還有 1 列沒選字幕組。')).toBeInTheDocument()
      expect(within(section).getByText('選了字幕組之後，這裡列出它的第一批。')).toBeInTheDocument()

      await user.click(within(section).getByRole('button', { name: /黒ネズミたち/ }))
      await user.click(within(section).getByRole('button', { name: '確認' }))

      expect(decisions).toEqual([{ approve: true, selection: null, subgroups: ['黒ネズミたち'] }])
    })

    it('preselects the assistant’s pick and lists the first batch of whichever is chosen', async () => {
      serve(keyword('ANi'), stored('approval-requested'), () => keyword('ANi'))
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '訂閱關鍵字搜尋' })
      expect(within(section).getByRole('button', { name: /^ANi/ })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
      expect(within(section).getByText('[ANi] Kimi - 01 [1080P]')).toBeInTheDocument()
      expect(within(section).getByText(/按下確認就送出第一批：2 個 torrent/)).toBeInTheDocument()

      await user.click(within(section).getByRole('button', { name: /黒ネズミたち/ }))

      expect(within(section).queryByText('[ANi] Kimi - 01 [1080P]')).toBeNull()
      expect(within(section).getByText(/按下確認就送出第一批：1 個 torrent/)).toBeInTheDocument()
      await user.click(within(section).getByRole('button', { name: '確認' }))
      expect(decisions).toEqual([{ approve: true, selection: null, subgroups: ['黒ネズミたち'] }])
    })

    it('a Mikan card counts the season of the subgroup chosen', async () => {
      const mikan = card({
        command: 'rss.subscribe_mikan',
        arguments: [
          {
            bangumi_id: 3310,
            subgroup_id: 583,
            media_id: 'tv:120089',
            route_id: 3,
            name: '',
            subgroup_name: '',
          },
        ],
        preview: {
          effect: 'reversible',
          flags: ['downloads'],
          checked: [true],
          external_fields: [[]],
          held_back: 0,
          torrents: [15],
          routes: [],
          subgroups: [
            {
              options: [
                { ...option('583', 'ANi', []), releases: 12, latest: '[ANi] SPY - 12' },
                { ...option('584', 'LoliHouse', []), releases: 15, latest: '[LoliHouse] SPY - 15' },
              ],
              preselected: '583',
              required: true,
            },
          ],
          existing: [],
        },
      })
      serve(mikan, stored('approval-requested'), () => mikan)
      const user = userEvent.setup()
      renderPanel()

      const section = await screen.findByRole('region', { name: '訂閱 Mikan 番組' })
      expect(within(section).getByText(/會送出整季：12 個 torrent/)).toBeInTheDocument()
      await user.click(within(section).getByRole('button', { name: /LoliHouse/ }))
      expect(within(section).getByText(/會送出整季：15 個 torrent/)).toBeInTheDocument()
      await user.click(within(section).getByRole('button', { name: '確認' }))
      expect(decisions).toEqual([{ approve: true, selection: null, subgroups: ['584'] }])
    })

    it('says which subscriptions the work already has', async () => {
      const twice = keyword('ANi', {
        preview: {
          ...keyword('ANi').preview,
          existing: [[{ feed_id: 9, name: 'acg.rip · Kimi', kind: 'acgrip', subgroup: '' }]],
        },
      })
      serve(twice, stored('approval-requested'), () => twice)
      renderPanel()

      const section = await screen.findByRole('region', { name: '訂閱關鍵字搜尋' })
      expect(within(section).getByText(/這部作品已經有這幾條訂閱/)).toBeInTheDocument()
      expect(within(section).getByText('acg.rip · Kimi')).toBeInTheDocument()
      expect(within(section).getByText(/每個字幕組都收/)).toBeInTheDocument()
    })
  })

  it('a card deleting a subscription names the feed and says the files stay', async () => {
    const gone = card({
      command: 'rss.delete_feed',
      arguments: [{ feed_id: 9 }],
      preview: {
        effect: 'irreversible',
        flags: ['settings'],
        checked: [false],
        external_fields: [[]],
        held_back: 0,
        torrents: [],
        routes: [],
        subgroups: [],
        existing: [],
      },
    })
    serve(gone, stored('approval-requested'), () => gone)
    renderPanel()

    const section = await screen.findByRole('region', { name: '刪除訂閱（RSS Feed）' })
    expect(await within(section).findByText('acg.rip · Kimi · ANi')).toBeInTheDocument()
    expect(within(section).getByText(/它的 5 筆紀錄一起刪/)).toBeInTheDocument()
    expect(within(section).getByText(/已經下載、入庫的檔案留著/)).toBeInTheDocument()
    expect(within(section).getByText('不可逆')).toBeInTheDocument()
  })
})

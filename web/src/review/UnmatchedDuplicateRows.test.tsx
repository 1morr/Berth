import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DuplicateReviewRow, ReviewQueue, UnmatchedReviewRow } from '../api/review'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

/**
 * 佇列的最後兩類（M2 票 08）：對不到的檔案與重複版本。頁面骨架與分段在 `ReviewPage.test.tsx`。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const QUEUE = 'GET /api/review'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'
const OVA =
  '/data/torrent/complete/anime/[Group] SPY×FAMILY S01/[Group] SPY×FAMILY OVA 2 [1080p].mkv'
const KNOWN =
  '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 01/SPY x FAMILY (2022) - S01E01 [1080p][CHT][Group].mkv'

function unmatched(overrides: Partial<UnmatchedReviewRow> = {}): UnmatchedReviewRow {
  return {
    kind: 'unmatched',
    ref: 11,
    reason: { code: 'left_in_place', params: {} },
    actions: ['import', 'extra', 'skip'],
    at: '2026-09-22T04:00:00Z',
    media_id: 'tv:120089',
    media_kind: 'tv',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: HASH,
    job_name: '[Group] SPY×FAMILY S01 [01-03][1080p][CHT]',
    path: OVA,
    file_kind: 'video',
    reasons: [{ code: 'own_numbered_special', params: {} }],
    ...overrides,
  }
}

function duplicate(overrides: Partial<DuplicateReviewRow> = {}): DuplicateReviewRow {
  return {
    kind: 'duplicate',
    ref: 21,
    reason: { code: 'same_version', params: {} },
    actions: ['replace', 'keep_both', 'skip'],
    at: '2026-09-22T05:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: HASH,
    job_name: '[Group] SPY×FAMILY S01E01 [1080p][CHT]',
    path: '/data/torrent/complete/anime/[Group] SPY×FAMILY S01E01 [1080p][CHT].mkv',
    season: 1,
    episode_start: 1,
    episode_end: null,
    known_path: KNOWN,
    known_season: 1,
    known_episode_start: 1,
    known_episode_end: null,
    ...overrides,
  }
}

function queue(rows: ReviewQueue['rows']): StubRoute {
  return { body: { rows, total: rows.length } }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [QUEUE]: queue([]),
    ...routes,
  })
}

function bodyOf(stub: ReturnType<typeof render>, url: string): unknown {
  const call = stub.mock.calls.find(([called]) => called === url)
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

describe('對不到的檔案', () => {
  it('在「要你決定」那一段，表單就攤在列上', async () => {
    render({ [QUEUE]: queue([unmatched()]) })
    renderApp('/review')

    const row = await screen.findByRole('article')

    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('要你決定')
    expect(within(row).getByText('對不到任何一集，留在 complete 原位')).toBeInTheDocument()
    const choice = within(row).getByRole('combobox', { name: '改成' })
    expect(
      within(choice)
        .getAllByRole('option')
        .map((node) => node.textContent),
    ).toEqual(['指派到某一集', '標記為特典', '忽略'])
    expect(within(row).getByRole('spinbutton', { name: '季' })).toBeInTheDocument()
  })

  it('指派為 S00E03：打 rematch 帶 job_file_id，成功之後那一列消失', async () => {
    let rows: ReviewQueue['rows'] = [unmatched()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/files/rematch': () => {
        rows = []
        return {
          body: { plan_id: 5, target_path: '/data/library/anime/x/Season 00/x - S00E03.mkv' },
        }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.type(within(row).getByRole('spinbutton', { name: '季' }), '0')
    await userEvent.type(within(row).getByRole('spinbutton', { name: '起集' }), '3')
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    // 對不到的檔案不在媒體庫裡，沒有東西會被拿掉——不另外確認，一下就送。
    expect(bodyOf(stub, '/api/files/rematch')).toEqual({
      job_file_id: 11,
      action: 'import',
      season: 0,
      episode_start: 3,
      episode_end: null,
    })
    expect(screen.getByText('已修正。')).toBeInTheDocument()
  })

  it('標記為特典或忽略時沒有季集可填', async () => {
    const stub = render({
      [QUEUE]: queue([unmatched()]),
      'POST /api/files/rematch': { body: { plan_id: 5, target_path: '' } },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.selectOptions(within(row).getByRole('combobox', { name: '改成' }), 'skip')
    expect(within(row).queryByRole('spinbutton')).not.toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/files/rematch')).toEqual({
        job_file_id: 11,
        action: 'skip',
        season: null,
        episode_start: null,
        episode_end: null,
      }),
    )
  })

  it('擋下來時就地說理由與原文', async () => {
    render({
      [QUEUE]: queue([unmatched()]),
      'POST /api/files/rematch': {
        status: 409,
        body: { detail: { reason: 'target_taken', detail: '/data/library/anime/x.mkv' } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.type(within(row).getByRole('spinbutton', { name: '季' }), '1')
    await userEvent.type(within(row).getByRole('spinbutton', { name: '起集' }), '2')
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    expect(
      await within(row).findByText(
        /目標位置上已經有別的檔案，Berth 不覆寫它： \/data\/library\/anime\/x\.mkv/,
      ),
    ).toBeInTheDocument()
  })

  it('電影的「指派」就是入庫，沒有季集', async () => {
    render({ [QUEUE]: queue([unmatched({ media_kind: 'movie' })]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    expect(within(row).getByRole('option', { name: '入庫' })).toBeInTheDocument()
    expect(within(row).queryByRole('spinbutton')).not.toBeInTheDocument()
  })

  it('字幕只能忽略', async () => {
    render({ [QUEUE]: queue([unmatched({ file_kind: 'subtitle', actions: ['skip'] })]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    const choice = within(row).getByRole('combobox', { name: '改成' })
    expect(
      within(choice)
        .getAllByRole('option')
        .map((node) => node.textContent),
    ).toEqual(['忽略'])
  })
})

describe('重複版本', () => {
  it('在「已入庫，等你看一眼」那一段，說得出它與媒體庫裡哪一份重複', async () => {
    render({ [QUEUE]: queue([duplicate()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('已入庫，等你看一眼')
    expect(within(row).getByRole('heading')).toHaveTextContent('SPY×FAMILY 間諜家家酒 S01E01')
    expect(within(row).getByText('媒體庫已經有同一集、同一組 Tags 的一份')).toBeInTheDocument()
    await userEvent.click(within(row).getByText('展開'))
    expect(within(row).getByText(`S01E01 · ${KNOWN}`)).toBeInTheDocument()
  })

  it('多集檔對同起始集的單集：理由說出 Jellyfin 會把後面那一集併掉', async () => {
    render({
      [QUEUE]: queue([duplicate({ reason: { code: 'span_clash', params: {} }, episode_end: 2 })]),
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    expect(
      within(row).getByText(/Jellyfin 12 會把它們併成同一集的兩個版本，後面那一集會從集列表消失/),
    ).toBeInTheDocument()
    expect(within(row).getByRole('heading')).toHaveTextContent('S01E01-E02')
  })

  it('取代舊版要就地確認一次，說出後果之後才送出', async () => {
    let rows: ReviewQueue['rows'] = [duplicate()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/duplicate/21/replace': () => {
        rows = []
        return { body: { plan_id: 9, target_path: KNOWN } }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '取代舊版' }))

    expect(stub.mock.calls.some(([url]) => url === '/api/review/duplicate/21/replace')).toBe(false)
    expect(within(row).getByText(/媒體庫裡舊的那一份會被拿掉/)).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '確定取代' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(screen.getByText('已取代，媒體庫裡換成新的一份了。')).toBeInTheDocument()
  })

  it('同一個版本的「保留兩者」與「跳過」一下就送', async () => {
    const stub = render({
      [QUEUE]: queue([duplicate()]),
      'POST /api/review/duplicate/21/keep_both': { body: { plan_id: 9, target_path: 'x [2].mkv' } },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '保留兩者' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/review/duplicate/21/keep_both')).toBe(
        true,
      ),
    )
  })

  it('範圍不同時「保留兩者」也要確認：那正是會讓一集從列表上消失的那一步', async () => {
    const stub = render({
      [QUEUE]: queue([duplicate({ reason: { code: 'span_clash', params: {} }, episode_end: 2 })]),
      'POST /api/review/duplicate/21/keep_both': { body: { plan_id: 9, target_path: 'x.mkv' } },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '保留兩者' }))

    expect(stub.mock.calls.some(([url]) => url === '/api/review/duplicate/21/keep_both')).toBe(
      false,
    )
    await userEvent.click(within(row).getByRole('button', { name: '仍然保留兩者' }))
    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/review/duplicate/21/keep_both')).toBe(
        true,
      ),
    )
  })

  it('另一個分頁先決定了：說理由，重問一次佇列', async () => {
    render({
      [QUEUE]: queue([duplicate()]),
      'POST /api/review/duplicate/21/skip': {
        status: 409,
        body: { detail: { reason: 'not_duplicate', detail: '21' } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '跳過' }))

    expect(await within(row).findByText(/多半是另一個分頁先決定了/)).toBeInTheDocument()
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Plan, PlanItem } from '../api/plans'
import type { AuditReviewRow, PlanReviewRow, ReviewQueue } from '../api/review'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const QUEUE = 'GET /api/review'
const PLAN = 'GET /api/plans/11'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'
const RELEASE = '[ANi] SPY×FAMILY - 05 [1080P][WEB-DL][AAC AVC][CHT]'
const FOLDER = 'SPY x FAMILY (2022) [tmdbid-120089]'
const PROPOSED = `${FOLDER}/Season 01/SPY x FAMILY (2022) - S01E05 [WEB][1080p][CHT][ANi].mkv`
const MOVED = `${FOLDER}/Season 02/SPY x FAMILY (2022) - S02E05 [WEB][1080p][CHT][ANi].mkv`

function planRow(overrides: Partial<PlanReviewRow> = {}): PlanReviewRow {
  return {
    kind: 'plan',
    ref: 11,
    reason: { code: 'low_confidence', params: { files: 0, low: 2, medium: 0 } },
    actions: ['approve', 'reject'],
    at: '2026-09-23T04:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: HASH,
    job_name: RELEASE,
    summary: {
      files: 0,
      high: 0,
      medium: 0,
      low: 2,
      actions: { review: 2, skip: 1 },
      review_reason: 'low_confidence',
    },
    ...overrides,
  }
}

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: 1,
    rel_path: `${RELEASE}.mkv`,
    kind: 'video',
    action: 'review',
    media_id: 'tv:120089',
    season: 1,
    episode_start: 5,
    episode_end: null,
    target_path: PROPOSED,
    confidence: 'low',
    reasons: [
      { code: 'absolute_cumulative', params: { number: 5, episode: 'S01E05' } },
      { code: 'absolute_within_first_season', params: { number: 5, episodes: 25, season: 1 } },
    ],
    audit: false,
    applied: false,
    actions: ['import', 'extra', 'unmatched', 'skip'],
    error: '',
    ...overrides,
  }
}

function plan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 11,
    job_hash: HASH,
    status: 'pending_review',
    engine: 'rules',
    engine_version: '0.1.0',
    created_at: '2026-09-23T04:00:00Z',
    media_kind: 'tv',
    summary: planRow().summary,
    items: [
      item(),
      item({
        id: 2,
        rel_path: 'fonts/a.ttf',
        kind: 'font',
        action: 'skip',
        season: null,
        episode_start: null,
        target_path: '',
        confidence: 'high',
        reasons: [{ code: 'classified', params: { kind: 'font' } }],
        actions: ['skip'],
      }),
    ],
    ...overrides,
  }
}

function audit(): AuditReviewRow {
  return {
    kind: 'audit',
    ref: 7,
    reason: { code: 'medium_auto_imported', params: {} },
    actions: ['confirm', 'undo'],
    at: '2026-09-20T04:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: 'b'.repeat(40),
    job_name: 'other',
    path: '/data/library/anime/x.mkv',
    source_path: '/data/torrent/complete/anime/x.mkv',
    season: 2,
    episode_start: 1,
    episode_end: null,
    reasons: [],
  }
}

function queue(rows: ReviewQueue['rows']): StubRoute {
  return { body: { rows, total: rows.length } }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [QUEUE]: queue([planRow()]),
    [PLAN]: { body: plan() },
    ...routes,
  })
}

/** 送出去的那一份 body（`stubApi` 的路由拿不到 request，所以從 fetch 的呼叫紀錄讀）。 */
function sent(stub: ReturnType<typeof render>, url: string): unknown {
  const call = stub.mock.calls.find(([called]) => called === url)
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

describe('審核佇列的 plan 那一類（M2 票 07）', () => {
  it('排在最前面那一段，說得出為什麼停下來', async () => {
    render({ [QUEUE]: queue([planRow(), audit()]) })
    renderApp('/review')

    const sections = await screen.findAllByRole('heading', { level: 2 })
    expect(sections.map((heading) => heading.textContent)).toEqual([
      expect.stringContaining('要你決定'),
      expect.stringContaining('已入庫，等你看一眼'),
    ])
    const [row] = screen.getAllByRole('article')
    expect(within(row).getByRole('heading', { level: 3 })).toHaveTextContent(
      'SPY×FAMILY 間諜家家酒',
    )
    expect(within(row).getByText(/有檔案的季集要你確認/)).toBeInTheDocument()
  })

  it('要人看的那一列攤開：提案、核准的話寫到哪裡、翻譯過的理由；其餘收著', async () => {
    render()
    renderApp('/review')
    const row = await screen.findByRole('article')

    expect(await within(row).findByText('1 列要你看')).toBeInTheDocument()
    expect(within(row).getByText('S01E05')).toBeInTheDocument()
    expect(within(row).getByText('核准後寫到')).toBeInTheDocument()
    expect(within(row).getByText(PROPOSED)).toBeInTheDocument()
    expect(within(row).getByText('各季集數依序累加，#5 落在 S01E05')).toBeInTheDocument()
    expect(within(row).getByText(/也可能是後面某季重新從 01 數的第 5 集/)).toBeInTheDocument()
    expect(within(row).getByText('其餘 1 個檔案')).toBeInTheDocument()
    // 收著的組展開才畫（M1.5 票 09 的長清單規則）。
    expect(within(row).queryByText('fonts/a.ttf')).not.toBeInTheDocument()
  })

  it('改季集 → 套用 → 那一列當場換成後端給的新路徑，焦點回到「改」', async () => {
    const edited = plan({
      items: [
        item({
          action: 'import',
          season: 2,
          target_path: MOVED,
          reasons: [...item().reasons, { code: 'set_by_user', params: {} }],
        }),
        plan().items[1],
      ],
    })
    const stub = render({ 'PUT /api/plans/11/items': { body: edited } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    // 待審核的列打開時預選「入庫」：多半就是要照提案入庫。
    expect(within(row).getByLabelText('處置')).toHaveValue('import')
    const season = within(row).getByLabelText('季')
    await userEvent.clear(season)
    await userEvent.type(season, '2')
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    expect(await within(row).findByText(MOVED)).toBeInTheDocument()
    expect(sent(stub, '/api/plans/11/items')).toEqual({
      items: [{ id: 1, action: 'import', season: 2, episode_start: 5, episode_end: null }],
    })
    expect(within(row).queryByRole('button', { name: '套用' })).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: `改 ${RELEASE}.mkv` })).toHaveFocus()
    expect(within(row).getByText('管理員改過這一列')).toBeInTheDocument()
    expect(screen.getByText('已套用，目標路徑更新了。')).toBeInTheDocument()
  })

  it('不合法的改動被拒絕時，就地說出理由，表單留著', async () => {
    render({
      'PUT /api/plans/11/items': {
        status: 422,
        body: { detail: { reason: 'episode_range_reversed', detail: `${RELEASE}.mkv` } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.type(within(row).getByLabelText('迄集'), '3')
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent('迄集比起集小。')
    expect(within(row).getByRole('button', { name: '套用' })).toBeInTheDocument()
  })

  it('略過不帶季集：選了別的處置，那三格就不畫也不送', async () => {
    const stub = render({ 'PUT /api/plans/11/items': { body: plan() } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.selectOptions(within(row).getByLabelText('處置'), 'skip')

    expect(within(row).queryByLabelText('季')).not.toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))
    await waitFor(() =>
      expect(sent(stub, '/api/plans/11/items')).toEqual({
        items: [{ id: 1, action: 'skip', season: null, episode_start: null, episode_end: null }],
      }),
    )
  })

  it('電影的計劃沒有季集可填', async () => {
    render({ [PLAN]: { body: plan({ media_kind: 'movie' }) } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))

    expect(within(row).getByLabelText('處置')).toHaveValue('import')
    expect(within(row).queryByLabelText('季')).not.toBeInTheDocument()
  })

  it('核准一次就送出：那一列從佇列消失，並對看不見畫面的人說一聲', async () => {
    let rows: ReviewQueue['rows'] = [planRow()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/plans/11/approve': () => {
        rows = []
        return { body: plan({ status: 'approved' }) }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(screen.getByText('已核准，開始入庫。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/approve')).toBe(true)
  })

  it('還有沒決定的列時，核准被擋下並說出是哪一個檔案', async () => {
    render({
      'POST /api/plans/11/approve': {
        status: 422,
        body: { detail: { reason: 'undecided', detail: 'theme.mkv' } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent(
      '還有列沒有決定，先改成入庫、略過或對不到： theme.mkv',
    )
  })

  it('拒絕要就地確認一次，說出它會丟掉改過的列', async () => {
    const stub = render({ 'POST /api/plans/11/reject': { status: 204, body: null } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '拒絕' }))

    expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/reject')).toBe(false)
    expect(within(row).getByText(/包括逐列改過的/)).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '確定拒絕' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/reject')).toBe(true),
    )
  })
})

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
    series: null,
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
    action: 'import',
    series: null,
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
    // 待審核的列打開時預選「入庫」：多半就是要照提案入庫。焦點進到那一格（M2 票 16 audit P2，M3 票 06）。
    expect(within(row).getByLabelText('處置')).toHaveValue('import')
    expect(within(row).getByLabelText('處置')).toHaveFocus()
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

  // M3 票 06：改到一半的列不會隨核准送出去（`approve` 不帶表單上的值），照原樣核准的是改之前的那一份。
  it('逐列改了還沒套用時，核准被擋下、說出是哪一列，不送出', async () => {
    const stub = render({ 'POST /api/plans/11/approve': { body: plan({ status: 'approved' }) } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    const season = within(row).getByLabelText('季')
    await userEvent.clear(season)
    await userEvent.type(season, '2')
    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent(
      `還有改動沒有套用，先按「套用」或「取消」：${RELEASE}.mkv`,
    )
    expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/approve')).toBe(false)
  })

  it('打開表單但沒改任何東西，不擋核准', async () => {
    const stub = render({ 'POST /api/plans/11/approve': { body: plan({ status: 'approved' }) } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/approve')).toBe(true),
    )
  })

  it('取消之後就不再擋', async () => {
    const stub = render({ 'POST /api/plans/11/approve': { body: plan({ status: 'approved' }) } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.type(within(row).getByLabelText('迄集'), '6')
    await userEvent.click(within(row).getByRole('button', { name: '取消' }))
    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/plans/11/approve')).toBe(true),
    )
  })

  // M3 票 06：Media 詳情那一份快取 5 分鐘內不重抓，不讓它失效的話回到詳情頁看到的是核准之前的入庫狀態。
  it('核准之後詳情頁那一份要重問', async () => {
    render({ 'POST /api/plans/11/approve': { body: plan({ status: 'approved' }) } })
    const { queryClient } = renderApp('/review')
    queryClient.setQueryData(['media', 'tv:120089'], { id: 'tv:120089' })
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '核准並入庫' }))

    await waitFor(() =>
      expect(queryClient.getQueryState(['media', 'tv:120089'])?.isInvalidated).toBe(true),
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

describe('從審核裡套用到 RSS Series（M3 票 14b）', () => {
  const SERIES = { id: 4, season: null, episode_offset: null }
  const CORRECTED = { season: 1, episode_offset: 12, moved: 0, replanned: 1, left: 0 }

  it('RSS Series 送的計劃多一格「套用到這個 RSS Series」、預設勾選，結果畫在頁上', async () => {
    const edited = { ...plan({ series: { ...SERIES, season: 1, episode_offset: 12 } }) }
    const stub = render({
      [PLAN]: { body: plan({ series: SERIES }) },
      'PUT /api/plans/11/items': { body: { ...edited, corrected: CORRECTED } },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    expect(within(row).getByRole('checkbox', { name: /套用到這個 RSS Series/ })).toBeChecked()
    const start = within(row).getByLabelText('起集')
    await userEvent.clear(start)
    await userEvent.type(start, '17')
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    const said = await screen.findByText(
      /^已修正，這個 RSS Series 改成第 1 季、集號偏移 \+12。 1 筆等審核的下載照新的值重新規劃了。 這一份照你改的留著/,
    )
    // 其餘的計劃從佇列上消失了：只念出來不夠，要看得見（`Said` 的 `shown`）。
    expect(said).not.toHaveClass('sr-only')
    expect(sent(stub, '/api/plans/11/items')).toEqual({
      items: [{ id: 1, action: 'import', season: 1, episode_start: 17, episode_end: null }],
      apply_to_series: true,
    })
  })

  it('取消勾選就只改這一列', async () => {
    const stub = render({
      [PLAN]: { body: plan({ series: SERIES }) },
      'PUT /api/plans/11/items': { body: { ...plan({ series: SERIES }), corrected: null } },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.click(within(row).getByRole('checkbox', { name: /套用到這個 RSS Series/ }))
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))

    expect(await screen.findByText('已套用，目標路徑更新了。')).toBeInTheDocument()
    expect(sent(stub, '/api/plans/11/items')).toEqual({
      items: [{ id: 1, action: 'import', season: 1, episode_start: 5, episode_end: null }],
    })
  })

  it('不是指派到某一集就沒有那一格；不是 RSS Series 送的也沒有', async () => {
    render({ [PLAN]: { body: plan({ series: SERIES }) } })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))
    await userEvent.selectOptions(within(row).getByLabelText('處置'), 'skip')

    expect(within(row).queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('一般的計劃沒有那一格', async () => {
    render()
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(await within(row).findByRole('button', { name: `改 ${RELEASE}.mkv` }))

    expect(within(row).queryByRole('checkbox')).not.toBeInTheDocument()
  })
})

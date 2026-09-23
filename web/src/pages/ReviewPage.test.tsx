import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Issue } from '../api/issues'
import type { AuditReviewRow, IssueReviewRow, ReviewQueue } from '../api/review'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const QUEUE = 'GET /api/review'
const TARGET =
  '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 02/SPY x FAMILY (2022) - S02E01.mkv'
const SOURCE = '/data/torrent/complete/anime/[ANi] SPY×FAMILY - 26.mkv'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'

function audit(overrides: Partial<AuditReviewRow> = {}): AuditReviewRow {
  return {
    kind: 'audit',
    ref: 7,
    reason: { code: 'medium_auto_imported', params: {} },
    actions: ['confirm', 'undo'],
    at: '2026-09-22T04:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: HASH,
    job_name: '[ANi] SPY×FAMILY - 26 [1080P][WEB-DL][AAC AVC][CHT]',
    path: TARGET,
    source_path: SOURCE,
    season: 2,
    episode_start: 1,
    episode_end: null,
    notes: ['absolute episode 26 is S02E01 by the cumulative count'],
    ...overrides,
  }
}

function issueRow(overrides: Partial<Issue> = {}): IssueReviewRow {
  const issue: Issue = {
    id: 3,
    type: 'library_link_missing',
    subject: TARGET,
    job_hash: HASH,
    ledger_id: 9,
    path: '/data/library/anime/Show/Season 01/Show - S01E02.mkv',
    detail: {},
    status: 'open',
    detected_at: '2026-09-21T04:00:00Z',
    actions: ['forget'],
    ...overrides,
  }
  return {
    kind: 'issue',
    ref: issue.id,
    reason: { code: issue.type, params: issue.detail },
    actions: issue.actions,
    at: issue.detected_at,
    issue,
  }
}

function queue(rows: ReviewQueue['rows'], total = rows.length): StubRoute {
  return { body: { rows, total } }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [QUEUE]: queue([]),
    ...routes,
  })
}

describe('審核佇列', () => {
  it('audit 那一列說得出是哪一集、為什麼在這裡、按得了什麼', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')

    const row = await screen.findByRole('article')

    expect(within(row).getByRole('heading')).toHaveTextContent('SPY×FAMILY 間諜家家酒 S02E01')
    // 理由是 code，句子是前端翻的（票上那一條驗收）。
    expect(within(row).getByText(/信心 medium，已自動入庫/)).toBeInTheDocument()
    expect(within(row).getByText('待確認')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '確認' })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '撤銷' })).toBeInTheDocument()
  })

  it('展開之後看得到兩條路徑與解析器的原文', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByText(TARGET)).toBeInTheDocument()
    expect(within(row).getByText(SOURCE)).toBeInTheDocument()
    expect(
      within(row).getByText('absolute episode 26 is S02E01 by the cumulative count'),
    ).toBeInTheDocument()
  })

  it('需要人動手的排前面：兩類各在自己那一段，順序照後端', async () => {
    render({ [QUEUE]: queue([audit(), issueRow()]) })
    renderApp('/review')

    await screen.findAllByRole('article')
    const headings = screen.getAllByRole('heading', { level: 2 }).map((node) => node.textContent)

    expect(headings).toEqual(['已入庫，等你看一眼1', '外面發生的事1'])
    // 空的段不畫：這一票還沒有 plan 那一類。
    expect(screen.queryByText('要你決定')).not.toBeInTheDocument()
  })

  it('按確認之後那一列消失，並對看不見畫面的人說一聲', async () => {
    let rows: ReviewQueue['rows'] = [audit()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/confirm': () => {
        rows = []
        return { status: 204, body: null }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '確認' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(screen.getByText('沒有事在等你。')).toBeInTheDocument()
    expect(screen.getByText('已確認，這一列從佇列上收掉了。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/confirm')).toBe(true)
  })

  it('撤銷要就地確認一次，說出後果之後才送出', async () => {
    let rows: ReviewQueue['rows'] = [audit()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/undo': () => {
        rows = []
        return { status: 204, body: null }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '撤銷' }))

    // 還沒送：第一下只展開後果。
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/undo')).toBe(false)
    expect(within(row).getByText(/complete 裡的檔案不動/)).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '確定撤銷' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/undo')).toBe(true)
  })

  it('撤銷失敗時那一列留著，說出理由與原文', async () => {
    render({
      [QUEUE]: queue([audit()]),
      'POST /api/review/audit/7/undo': {
        status: 409,
        body: { detail: { reason: 'unlink_failed', detail: 'Permission denied' } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '撤銷' }))
    await userEvent.click(within(row).getByRole('button', { name: '確定撤銷' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent(
      '媒體庫裡那個檔案拿不掉，所以什麼都沒改。 Permission denied',
    )
  })

  it('issue 那一類就地按，按完那一列從佇列消失、不跳頁', async () => {
    let rows: ReviewQueue['rows'] = [issueRow()]
    render({
      [QUEUE]: () => queue(rows),
      'GET /api/issues': { body: [] },
      'POST /api/issues/3/resolve': () => {
        rows = []
        return { body: { ...issueRow().issue, status: 'resolved', actions: [] } }
      },
    })
    const { router } = renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '承認刪除並清帳本' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(router.state.location.pathname).toBe('/review')
    // 那一列消失了，結果要給看不見畫面的人另外說一次（code-review Standards 軸）。
    expect(screen.getByText('已處理，這一件從清單上收掉了。')).toBeInTheDocument()
  })

  it('超過上限時說出只列了前幾件', async () => {
    render({ [QUEUE]: queue([audit()], 201) })
    renderApp('/review')

    expect(await screen.findByText('只列出最舊的 1 件，共 201 件。')).toBeInTheDocument()
  })

  it('空的時候說沒有事在等你', async () => {
    render()
    renderApp('/review')

    expect(await screen.findByText('沒有事在等你。')).toBeInTheDocument()
  })
})

describe('誰看得到審核佇列', () => {
  it('admin 的導覽列有入口', async () => {
    render()
    renderApp('/review')

    expect(await screen.findByRole('link', { name: '審核' })).toBeInTheDocument()
  })

  it('user 看不到入口，直接開網址會被送走', async () => {
    render({ 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } })
    const { router } = renderApp('/review')

    await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
    expect(screen.queryByRole('link', { name: '審核' })).not.toBeInTheDocument()
  })
})

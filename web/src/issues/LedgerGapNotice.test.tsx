import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Issue, LedgerGap, RebuildReport, ReconcileStatus } from '../api/issues'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

// 重裝之後在畫面上把帳本找回來（M4 票 60，`.scratch/m4/ledger-rebuild-shape.md`）。

const GAP = 'GET /api/issues/rebuild-ledger'
const REBUILD = 'POST /api/issues/rebuild-ledger'
const NEVER_RUN: ReconcileStatus = { current: null, last: null }

function report(overrides: Partial<RebuildReport> = {}): RebuildReport {
  return {
    known: 0,
    claimed: 5,
    unmatched: { no_source: 1 },
    skipped: [],
    unread_complete: [],
    undecided: 0,
    ...overrides,
  }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    'GET /api/issues': { body: [] },
    'GET /api/reconcile': { body: NEVER_RUN },
    [GAP]: { body: { unknown: 0 } satisfies LedgerGap },
    ...routes,
  })
}

function notice() {
  return screen.getByRole('region', { name: '帳本不認得的檔案' })
}

describe('待處理頁的「從媒體庫重建帳本」', () => {
  it('帳本認得每一個檔案時什麼都不畫', async () => {
    const api = render()
    renderApp('/issues')

    await screen.findByText('這個程序起來之後還沒有對過帳。')
    await waitFor(() =>
      expect(api.mock.calls.some(([url]) => url === '/api/issues/rebuild-ledger')).toBe(true),
    )
    expect(screen.queryByRole('region', { name: '帳本不認得的檔案' })).not.toBeInTheDocument()
  })

  it('說有幾個、為什麼、按下去會怎樣', async () => {
    render({ [GAP]: { body: { unknown: 6 } } })
    renderApp('/issues')

    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })

    expect(
      within(region).getByText(
        '媒體庫裡有 6 個檔案不在 Berth 的帳本上。多半是重裝過 Berth 或資料庫遺失：檔案還在，紀錄沒了。',
      ),
    ).toBeVisible()
    expect(within(region).getByRole('button', { name: '從媒體庫重建帳本' })).toBeVisible()
    expect(within(region).getByText(/只加不刪，可以重按/)).toBeVisible()
  })

  it('按下去說找回幾個、幾個變成非受管檔案，清單重抓', async () => {
    let gap = 6
    const api = render({
      [GAP]: () => ({ body: { unknown: gap } }),
      [REBUILD]: () => {
        gap = 0
        return { body: report() }
      },
    })
    renderApp('/issues')
    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })
    const listed = api.mock.calls.filter(([url]) => url === '/api/issues').length

    await userEvent.click(within(region).getByRole('button', { name: '從媒體庫重建帳本' }))

    expect(await within(notice()).findByText('找回 5 個檔案。')).toBeVisible()
    expect(
      within(notice()).getByText('1 個配不上，列進待處理的「非受管檔案」，每一件寫著理由。'),
    ).toBeVisible()
    // 結果留著；按鈕與那一句不再畫——重建做完了。
    expect(within(notice()).queryByRole('button')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(api.mock.calls.filter(([url]) => url === '/api/issues').length).toBeGreaterThan(
        listed,
      ),
    )
  })

  it('再按一次什麼都沒多時說帳本已經認得每一個檔案', async () => {
    render({
      [GAP]: { body: { unknown: 1 } },
      [REBUILD]: { body: report({ known: 6, claimed: 0, unmatched: {} }) },
    })
    renderApp('/issues')
    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })

    await userEvent.click(within(region).getByRole('button', { name: '從媒體庫重建帳本' }))

    expect(
      await within(notice()).findByText('沒有要找回的檔案：帳本已經認得媒體庫裡的每一個檔案。'),
    ).toBeVisible()
  })

  it('有地方讀不到時另說一句，原文收進技術細節', async () => {
    render({
      [GAP]: { body: { unknown: 6 } },
      [REBUILD]: {
        body: report({
          skipped: ['Anime (/data/library/anime): [Errno 13] Permission denied'],
          undecided: 2,
        }),
      },
    })
    renderApp('/issues')
    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })

    await userEvent.click(within(region).getByRole('button', { name: '從媒體庫重建帳本' }))

    expect(
      await within(notice()).findByText(
        '有地方讀不到，那裡的檔案這一次沒有比。修好掛載之後再按一次。',
      ),
    ).toBeVisible()
    expect(within(notice()).getByText(/2 個說不出有沒有來源/)).toBeVisible()
    await userEvent.click(within(notice()).getByText('技術細節'))
    expect(
      within(notice()).getByText('Anime (/data/library/anime): [Errno 13] Permission denied'),
    ).toBeVisible()
  })

  it('有地方讀不到時不說「帳本已經認得每一個檔案」', async () => {
    render({
      [GAP]: { body: { unknown: 6 } },
      [REBUILD]: {
        body: report({
          claimed: 0,
          unmatched: {},
          skipped: ['Anime (/data/library/anime): [Errno 13] Permission denied'],
        }),
      },
    })
    renderApp('/issues')
    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })

    await userEvent.click(within(region).getByRole('button', { name: '從媒體庫重建帳本' }))

    expect(
      await within(notice()).findByText(
        '有地方讀不到，那裡的檔案這一次沒有比。修好掛載之後再按一次。',
      ),
    ).toBeVisible()
    expect(within(notice()).queryByText(/帳本已經認得/)).not.toBeInTheDocument()
  })

  it('對帳正在跑時說等它跑完', async () => {
    render({
      [GAP]: { body: { unknown: 6 } },
      [REBUILD]: {
        status: 409,
        body: { detail: { reason: 'reconcile_running', detail: 'a reconcile is running' } },
      },
    })
    renderApp('/issues')
    const region = await screen.findByRole('region', { name: '帳本不認得的檔案' })

    await userEvent.click(within(region).getByRole('button', { name: '從媒體庫重建帳本' }))

    expect(await within(notice()).findByText('上一輪對帳還在跑。等它跑完再按。')).toBeVisible()
    expect(within(notice()).getByRole('button', { name: '從媒體庫重建帳本' })).toBeVisible()
  })

  it('英文介面', async () => {
    await i18next.changeLanguage('en')
    try {
      render({ [GAP]: { body: { unknown: 6 } }, [REBUILD]: { body: report() } })
      renderApp('/issues')

      const region = await screen.findByRole('region', { name: 'Files the ledger does not know' })
      expect(
        within(region).getByText(/6 files in the library are not in Berth’s ledger/),
      ).toBeVisible()
      await userEvent.click(
        within(region).getByRole('button', { name: 'Rebuild the ledger from the library' }),
      )
      expect(await within(region).findByText('Recovered 5 files.')).toBeVisible()
      expect(
        within(region).getByText(
          '1 did not match and is listed under Issues as an unmanaged file, with the reason.',
        ),
      ).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

describe('無主 torrent 那一列說清楚認領會做什麼', () => {
  const ORPHAN: Issue = {
    id: 3,
    type: 'unknown_torrent',
    subject: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b',
    job_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b',
    ledger_id: null,
    path: '',
    detail: { name: 'Night Of The Living Dead (1968) [BluRay] [720p] [YTS.AM]' },
    status: 'open',
    detected_at: '2026-10-07T14:40:28Z',
    actions: ['claim_torrent'],
    query: 'Night Of The Living Dead',
  }

  it('按鈕上面就說，不收進展開', async () => {
    render({ 'GET /api/issues': { body: [ORPHAN] } })
    renderApp('/issues')

    const row = await screen.findByRole('article')

    expect(
      within(row).getByText(/Berth 建一筆下載接手這個 torrent，接下來照常規劃、入庫/),
    ).toBeVisible()
    expect(within(row).getByText(/重裝過 Berth 的話先從媒體庫重建帳本/)).toBeVisible()
  })

  it('別種 Issue 不說', async () => {
    render({
      'GET /api/issues': { body: [{ ...ORPHAN, type: 'orphan_complete', actions: ['adopt'] }] },
    })
    renderApp('/issues')

    const row = await screen.findByRole('article')

    expect(within(row).queryByText(/接手這個 torrent/)).not.toBeInTheDocument()
  })

  it('英文介面', async () => {
    await i18next.changeLanguage('en')
    try {
      render({ 'GET /api/issues': { body: [ORPHAN] } })
      renderApp('/issues')

      const row = await screen.findByRole('article')

      expect(
        within(row).getByText(/Berth creates a download that takes over this torrent/),
      ).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

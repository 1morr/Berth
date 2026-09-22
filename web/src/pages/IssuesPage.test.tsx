import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Issue, ReconcileStatus } from '../api/issues'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const ISSUES = 'GET /api/issues'
const RECONCILE = 'GET /api/reconcile'
const START = 'POST /api/reconcile'

const TARGET =
  '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 01/SPY x FAMILY (2022) - S01E01.mkv'
const SOURCE = '/data/torrent/complete/anime/SPY.x.FAMILY.S01E01.mkv'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'

function issue(overrides: Partial<Issue> = {}): Issue {
  return {
    id: 1,
    type: 'library_link_missing',
    subject: TARGET,
    job_hash: HASH,
    ledger_id: 7,
    path: TARGET,
    detail: { source: SOURCE, season: 1, episode: 1 },
    status: 'open',
    detected_at: '2026-09-22T04:00:00Z',
    actions: ['relink', 'forget', 'delete_complete'],
    ...overrides,
  }
}

const NEVER_RUN: ReconcileStatus = { current: null, last: null }

function finished(overrides: Partial<ReconcileStatus['last'] & object> = {}): ReconcileStatus {
  return {
    current: null,
    last: {
      id: 1,
      started_at: '2026-09-22T04:00:00Z',
      finished_at: '2026-09-22T04:00:09Z',
      sides: [
        { side: 'ledger', counted: 42, unavailable: '', skipped: [] },
        { side: 'client', counted: 3, unavailable: '', skipped: [] },
        { side: 'complete', counted: 8, unavailable: '', skipped: [] },
        { side: 'library', counted: 42, unavailable: '', skipped: [] },
      ],
      opened: 1,
      updated: 0,
      ...overrides,
    },
  }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [ISSUES]: { body: [] },
    [RECONCILE]: { body: NEVER_RUN },
    ...routes,
  })
}

describe('待處理頁', () => {
  it('一列說出它是什麼、按得了什麼', async () => {
    render({ [ISSUES]: { body: [issue()] } })
    renderApp('/issues')

    const row = await screen.findByRole('article')

    expect(within(row).getByText(/媒體庫裡少了這個檔案/)).toBeInTheDocument()
    // 掃視時只看得到檔名，完整路徑在展開區——路徑會把一列撐成三行。
    expect(within(row).getByRole('heading')).toHaveTextContent('SPY x FAMILY (2022) - S01E01.mkv')
    for (const label of ['重新鏈接', '承認刪除並清帳本', '連 complete 一起刪', '忽略'])
      expect(within(row).getByRole('button', { name: label })).toBeInTheDocument()
  })

  it('狀態不只靠顏色：型別有一個模板字標籤', async () => {
    // DESIGN.md 的 The Triple Encoding Rule：轉成灰階仍然讀得出來。
    render({ [ISSUES]: { body: [issue()] } })
    renderApp('/issues')

    const row = await screen.findByRole('article')

    expect(within(row).getByText('鏈接遺失')).toBeInTheDocument()
  })

  it('後端沒給的動作就不畫出來', async () => {
    // 按下去會被拒絕的按鈕不該存在：`actions` 由後端算（`services/issues._actions`）。
    render({ [ISSUES]: { body: [issue({ actions: ['forget'] })] } })
    renderApp('/issues')

    const row = await screen.findByRole('article')

    expect(within(row).getByRole('button', { name: '承認刪除並清帳本' })).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: '重新鏈接' })).not.toBeInTheDocument()
    // 忽略永遠在：一件按不了任何一顆的 Issue 仍然要收得掉。
    expect(within(row).getByRole('button', { name: '忽略' })).toBeInTheDocument()
  })

  it('展開之後看得到完整路徑與來源', async () => {
    render({ [ISSUES]: { body: [issue()] } })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByText(TARGET)).toBeInTheDocument()
    expect(within(row).getByText(SOURCE)).toBeInTheDocument()
  })

  it('按下重新鏈接之後那一列不見了', async () => {
    let listed = [issue()]
    render({
      [ISSUES]: () => ({ body: listed }),
      'POST /api/issues/1/resolve': () => {
        listed = []
        return { body: issue({ status: 'resolved', actions: [] }) }
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新鏈接' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
  })

  it('修不好的時候那一列留著，並說出為什麼', async () => {
    // **畫面說修好了而媒體庫沒變，是這一票最糟的結果**：失敗時它仍然是 open。
    render({
      [ISSUES]: { body: [issue()] },
      // 後端的拒絕包在 `HTTPException` 的 `detail` 裡（`api/issues.issue_refusal`）。
      'POST /api/issues/1/resolve': {
        status: 409,
        body: { detail: { reason: 'source_missing', detail: 'no such file' } },
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新鏈接' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/complete 裡的來源檔也不在了/)
    expect(screen.getByRole('article')).toBeInTheDocument()
  })

  it('連 complete 一起刪要先確認，而確認說清楚單位是整筆下載', async () => {
    const stub = render({ [ISSUES]: { body: [issue()] } })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '連 complete 一起刪' }))

    expect(screen.getByText(/這會移除這一筆下載的全部/)).toBeInTheDocument()
    // 還沒按確認，所以什麼都還沒送出去。
    expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(0)
  })

  it('確認之後才真的送出去', async () => {
    const stub = render({
      [ISSUES]: { body: [issue()] },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')
    await userEvent.click(within(row).getByRole('button', { name: '連 complete 一起刪' }))

    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it('空的時候說的是「都對得上」，不是「沒有資料」', async () => {
    render({ [RECONCILE]: { body: finished() } })
    renderApp('/issues')

    expect(
      await screen.findByText(/沒有要決定的事。上一次對帳時帳本與磁碟對得上/),
    ).toBeInTheDocument()
  })

  it('還沒對過帳的空清單說的是另一句話', async () => {
    render()
    renderApp('/issues')

    expect(
      await screen.findByText(/沒有要決定的事。這個程序起來之後還沒有對過帳/),
    ).toBeInTheDocument()
  })
})

describe('對帳橫幅', () => {
  it('跑完之後四方都說得出比了幾筆', async () => {
    render({ [RECONCILE]: { body: finished() } })
    renderApp('/issues')

    // 在橫幅裡找，不是整頁：`媒體庫` 也是導覽列上的一個連結。
    const banner = await screen.findByRole('list', { name: '對帳進度' })
    for (const label of ['帳本', 'qBittorrent', 'COMPLETE', '媒體庫'])
      expect(within(banner).getByText(label)).toBeInTheDocument()
    expect(within(banner).getAllByText(/比了 42 筆/)).toHaveLength(2)
  })

  it('問不到的那一方說出來，而不是報成 0 筆', async () => {
    // brief §16.2：**不把「問不到」誤判成「不見了」**。畫面要分得出「都好好的」與「根本沒比」。
    render({
      [RECONCILE]: {
        body: finished({
          sides: [
            { side: 'ledger', counted: 42, unavailable: '', skipped: [] },
            {
              side: 'client',
              counted: 0,
              unavailable: 'qBittorrent did not answer: connection refused',
              skipped: [],
            },
            { side: 'complete', counted: 8, unavailable: '', skipped: [] },
            { side: 'library', counted: 42, unavailable: '', skipped: [] },
          ],
        }),
      },
    })
    renderApp('/issues')

    expect(await screen.findByText('問不到')).toBeInTheDocument()
    expect(screen.getByText(/connection refused/)).toBeInTheDocument()
    expect(screen.queryByText(/比了 0 筆/)).not.toBeInTheDocument()
  })

  it('跳過的那一條 Route 說得出是哪一條', async () => {
    render({
      [RECONCILE]: {
        body: finished({
          sides: [
            { side: 'ledger', counted: 42, unavailable: '', skipped: [] },
            { side: 'client', counted: 3, unavailable: '', skipped: [] },
            { side: 'complete', counted: 8, unavailable: '', skipped: [] },
            {
              side: 'library',
              counted: 0,
              unavailable: '',
              skipped: ['Anime (/data/library/anime) is not there; is the volume mounted?'],
            },
          ],
        }),
      },
    })
    renderApp('/issues')

    expect(await screen.findByText(/Anime .* is not there/)).toBeInTheDocument()
  })

  it('按下立刻對帳會開一輪', async () => {
    const stub = render({
      [START]: {
        status: 202,
        body: {
          id: 2,
          started_at: '2026-09-22T09:00:00Z',
          finished_at: null,
          sides: [],
          opened: 0,
          updated: 0,
        },
      },
    })
    renderApp('/issues')

    await userEvent.click(await screen.findByRole('button', { name: '立刻對帳' }))

    await waitFor(() => expect(sent(stub, START)).toBe(1))
    expect(await screen.findByRole('button', { name: '對帳中…' })).toBeInTheDocument()
  })

  it('上一輪還在跑的時候說得出來', async () => {
    render({
      [RECONCILE]: {
        body: {
          current: {
            id: 2,
            started_at: '2026-09-22T09:00:00Z',
            finished_at: null,
            sides: [{ side: 'ledger', counted: 42, unavailable: '', skipped: [] }],
            opened: 0,
            updated: 0,
          },
          last: null,
        },
      },
    })
    renderApp('/issues')

    expect(await screen.findByRole('button', { name: '對帳中…' })).toBeInTheDocument()
    const banner = screen.getByRole('list', { name: '對帳進度' })
    expect(within(banner).getByText('帳本')).toBeInTheDocument()
  })
})

/** 這一支端點被送出去幾次。 */
function sent(stub: ReturnType<typeof stubApi>, key: string) {
  const [method, path] = key.split(' ')
  return stub.mock.calls.filter(
    ([input, init]) => (init?.method ?? 'GET') === method && String(input) === path,
  ).length
}

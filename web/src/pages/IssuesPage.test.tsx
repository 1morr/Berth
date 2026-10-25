import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'

import { reconcileQueryOptions, type Issue, type ReconcileStatus } from '../api/issues'
import { HEALTHY, REQUEST_FAILURES, stubApi, type StubRoutes } from '../test/fetch'
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
    query: '',
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
        { side: 'jellyfin', counted: 30, unavailable: '', skipped: [] },
      ],
      opened: 1,
      updated: 0,
      ...overrides,
    },
  }
}

function render(routes: StubRoutes = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [ISSUES]: { body: [] },
    [RECONCILE]: { body: NEVER_RUN },
    ...routes,
  })
}

describe('待處理頁', () => {
  // M2 票 16 的 critique：按下去的那一顆跟著整列消失，焦點不能掉回 `body`（同 `/review`）。
  it('按完那一件消失之後，焦點落在下一件', async () => {
    let open = [issue(), issue({ id: 2, path: `${TARGET}.2`, subject: `${TARGET}.2` })]
    render({
      [ISSUES]: () => ({ body: open }),
      'POST /api/issues/1/ignore': () => {
        const [first] = open
        open = open.slice(1)
        return { body: { ...first, status: 'ignored' } }
      },
    })
    renderApp('/issues')
    const [first] = await screen.findAllByRole('article')

    within(first).getByRole('button', { name: '忽略' }).focus()
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1))
    await waitFor(() => expect(screen.getByRole('article')).toHaveFocus())
  })

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

  it('所屬下載那一格連到它的詳情頁（M2 票 12）', async () => {
    render({ [ISSUES]: { body: [issue()] } })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByRole('link', { name: HASH })).toHaveAttribute('href', `/jobs/${HASH}`)
  })

  it('無主的 torrent 定義上沒有下載：hash 只是字，不連到一頁一定是空的詳情', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'unknown_torrent',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: { name: '[Group] Not Ours - 01', category: 'berth-anime' },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByText(HASH)).toBeInTheDocument()
    expect(within(row).queryByRole('link', { name: HASH })).toBeNull()
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

  // M3 票 06：修好之後 Media 詳情的入庫狀態要跟著變；那一份快取 5 分鐘內不重抓。
  it('修好之後詳情頁那一份要重問', async () => {
    let listed = [issue()]
    render({
      [ISSUES]: () => ({ body: listed }),
      'POST /api/issues/1/resolve': () => {
        listed = []
        return { body: issue({ status: 'resolved', actions: [] }) }
      },
    })
    const { queryClient } = renderApp('/issues')
    queryClient.setQueryData(['media', 'tv:120089'], { id: 'tv:120089' })
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新鏈接' }))

    await waitFor(() =>
      expect(queryClient.getQueryState(['media', 'tv:120089'])?.isInvalidated).toBe(true),
    )
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

  it('刪 complete 底下的孤兒目錄要先確認，並說清楚刪的是一整棵', async () => {
    const folder = '/data/torrent/complete/anime/Someone Else'
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            subject: folder,
            path: folder,
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['delete_orphan'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '刪除這個目錄' }))
    expect(screen.getByText(/complete 底下這一整個目錄/)).toBeInTheDocument()
    expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(0)

    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))
    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it('以硬鏈接取代也要先確認：媒體庫那一份複製品會消失', async () => {
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'inode_mismatch',
            detail: { source: SOURCE, same_size: true },
            actions: ['replace_with_link'],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '以硬鏈接取代' }))

    expect(screen.getByText(/複製品本身會消失/)).toBeInTheDocument()
    expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(0)
  })

  it('不刪東西的按鈕按下去就送出', async () => {
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'jellyfin_item_unresolved',
            detail: { attempts: 6 },
            actions: ['relook', 'rescan'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新反查' }))

    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it('反查失敗說出重新掃描掃多大，會掃整台的那一種照實說（M4 票 62）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'jellyfin_item_unresolved',
            detail: { attempts: 6 },
            actions: ['relook', 'rescan'],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText(/只刷新這條 Route 的媒體庫/)).toBeInTheDocument()
    expect(within(row).getByText(/整台伺服器/)).toBeInTheDocument()
  })

  it('回驗不符說出兩邊各自認成什麼、差在哪，並給重新反查（M3 票 17）', async () => {
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'jellyfin_item_mismatch',
            detail: {
              differs: ['episode'],
              ledger: { season: 1, episode_start: 3, episode_end: 4, tmdb: '120089' },
              jellyfin: {
                season: 1,
                episode_start: 3,
                episode_end: null,
                tmdb: '120089',
                item: 'abc',
                name: 'Episode 3',
              },
            },
            actions: ['relook'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText('回驗不符')).toBeInTheDocument()
    expect(within(row).getByText('S01E03-E04 · TMDB 120089')).toBeInTheDocument()
    expect(within(row).getByText('S01E03 · TMDB 120089')).toBeInTheDocument()
    expect(within(row).getByText('集號')).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: '重新掃描媒體庫' })).not.toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '重新反查' }))
    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it('complete 底下的路徑不叫媒體庫路徑', async () => {
    const folder = '/data/torrent/complete/anime/Someone Else'
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            subject: folder,
            path: folder,
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['delete_orphan'],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText('complete 路徑')).toBeInTheDocument()
    expect(within(row).queryByText('媒體庫路徑')).not.toBeInTheDocument()
  })

  it('沒有路徑的無主 torrent 以它的名字認，不是一串 hash', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'unknown_torrent',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: { name: '[Group] Not Ours - 01', category: 'berth-anime' },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByRole('heading', { name: '[Group] Not Ours - 01' })).toBeInTheDocument()
    expect(within(row).queryByText('媒體庫路徑')).not.toBeInTheDocument()
  })

  it('管線那三種的按鈕照後端給的畫，不刪東西的按下去就送出（M2 票 09c）', async () => {
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'missing_files',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: { name: '[ANi] SPY×FAMILY - 13', client_state: 'missingFiles' },
            actions: ['recheck', 'accept_loss'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByRole('button', { name: '承認遺失' })).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '重新校驗' }))

    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it('問不到 qBittorrent 時那一列留著，並說出為什麼', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'client_removed',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: { name: '[ANi] SPY×FAMILY - 13' },
            actions: ['resubmit', 'accept_removal'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': {
        status: 502,
        body: { detail: { reason: 'client_unreachable', detail: 'connection refused' } },
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新送單' }))

    expect(
      await within(row).findByText(
        '問不到 qBittorrent，所以什麼都沒有做。先確認它還活著。 connection refused',
      ),
    ).toBeInTheDocument()
  })

  it('TVDB 那一件以 Route 認，並說得出去 Jellyfin 哪裡修', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'library_uses_tvdb',
            subject: '/data/library/anime',
            path: '/data/library/anime',
            job_hash: '',
            ledger_id: null,
            detail: { route: 'Anime', library: '動畫', fetchers: ['TheTVDB'] },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByRole('heading', { name: 'Anime' })).toBeInTheDocument()
    await userEvent.click(within(row).getByText('Anime'))
    expect(within(row).getByText('TheTVDB')).toBeInTheDocument()
    expect(within(row).getByText(/到 Jellyfin 的媒體庫設定把 TVDB/)).toBeInTheDocument()
    // 沒有 Berth 按得了的修法：只剩忽略。
    expect(
      within(row)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['忽略'])
  })

  it('磁碟空間那一件說出剩多少、門檻多少，路徑叫量的目錄', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'low_disk_space',
            subject: '/data/torrent/complete',
            path: '/data/torrent/complete',
            job_hash: '',
            ledger_id: null,
            detail: { free: 3 * 1024 ** 3, min_free: 10 * 1024 ** 3 },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText('量的目錄')).toBeInTheDocument()
    expect(within(row).queryByText('媒體庫路徑')).not.toBeInTheDocument()
    expect(within(row).getByText('剩下')).toBeInTheDocument()
    expect(within(row).getByText('門檻')).toBeInTheDocument()
  })

  it('第一批卡住以 Series 認，說出停在哪、為什麼，下一步連到那一筆下載（M4 票 129）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'first_batch_stuck',
            subject: '7',
            path: '',
            job_hash: HASH,
            ledger_id: null,
            detail: {
              series: 7,
              name: '[LoliHouse] Kimi to Koishitai - 11',
              job: '[LoliHouse] Kimi to Koishitai - 11 [WebRip 1080p]',
              state: 'submit_failed',
              error: 'qBittorrent refused the torrent',
              since: '2026-10-20T03:00:00+00:00',
            },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(
      within(row).getByRole('heading', { name: '[LoliHouse] Kimi to Koishitai - 11' }),
    ).toBeInTheDocument()
    expect(within(row).getByText('RSS Series 的第一批卡住了，一直等人確認')).toBeInTheDocument()
    expect(within(row).getByText('第一批卡住')).toBeInTheDocument()
    await userEvent.click(within(row).getByText('[LoliHouse] Kimi to Koishitai - 11'))
    expect(within(row).getByText('送單失敗')).toBeInTheDocument()
    expect(within(row).getByText('qBittorrent refused the torrent')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: HASH })).toHaveAttribute('href', `/jobs/${HASH}`)
    expect(within(row).getByText(/重試或刪掉它/)).toBeInTheDocument()
    // 出路不在這一列上：只剩忽略。
    expect(
      within(row)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['忽略'])
  })

  it('送單失敗以那一筆下載認，說出原因與下一步，按得了重試與放棄（M5 票 03）', async () => {
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'submit_failed',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: {
              name: '[SweetSub] Kusuriya no Hitorigoto - 05',
              state: 'submit_failed',
              error: 'qBittorrent refused the torrent: 415',
              since: '2026-10-20T03:00:00+00:00',
            },
            actions: ['retry', 'abandon'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(
      within(row).getByRole('heading', { name: '[SweetSub] Kusuriya no Hitorigoto - 05' }),
    ).toBeInTheDocument()
    expect(within(row).getByText('送單失敗')).toBeInTheDocument()
    expect(
      within(row).getByText('這一筆下載送不進 qBittorrent，也不會再自動重送'),
    ).toBeInTheDocument()
    await userEvent.click(within(row).getByText('[SweetSub] Kusuriya no Hitorigoto - 05'))
    expect(within(row).getByText('qBittorrent refused the torrent: 415')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: HASH })).toHaveAttribute('href', `/jobs/${HASH}`)
    expect(within(row).getByText(/到作品頁重新搜一次/)).toBeInTheDocument()
    expect(
      within(row)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['重試', '放棄這一筆', '忽略'])

    // 放棄不刪東西（四個旗標全不勾），所以不必就地確認：按下去就送出。
    await userEvent.click(within(row).getByRole('button', { name: '放棄這一筆' }))

    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
  })

  it.each([
    [
      'import_failed',
      '入庫失敗',
      '這一筆下載完了，入庫沒有成功',
      /從還沒鏈接的那幾個接著做/,
      ['重試', '放棄這一筆', '忽略'],
    ],
    ['stalled', '停滯', '這一筆下載停滯超過一天了', /多半是沒有人在做種/, ['放棄這一筆', '忽略']],
  ] as const)(
    '%s 說出它是哪一種與下一步（M5 票 03）',
    async (type, label, sentence, next, buttons) => {
      render({
        [ISSUES]: {
          body: [
            issue({
              type,
              subject: HASH,
              path: '',
              ledger_id: null,
              detail: {
                name: '[SweetSub] Kusuriya no Hitorigoto - 05',
                state: type,
                error: '',
                since: '2026-10-20T03:00:00+00:00',
              },
              actions: type === 'stalled' ? ['abandon'] : ['retry', 'abandon'],
            }),
          ],
        },
      })
      renderApp('/issues')
      const row = await screen.findByRole('article')

      expect(within(row).getByText(label)).toBeInTheDocument()
      expect(within(row).getByText(sentence)).toBeInTheDocument()
      await userEvent.click(within(row).getByText('[SweetSub] Kusuriya no Hitorigoto - 05'))
      expect(within(row).getByText(next)).toBeInTheDocument()
      // 沒有原文時不畫「原因」那一行。
      expect(within(row).queryByText('原因')).not.toBeInTheDocument()
      expect(
        within(row)
          .getAllByRole('button')
          .map((button) => button.textContent),
      ).toEqual([...buttons])
    },
  )

  it('卡住的 Job 重試時磁碟不夠，那一列留著並說出為什麼（M5 票 03）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'import_failed',
            subject: HASH,
            path: '',
            ledger_id: null,
            detail: { name: '[SweetSub] Kusuriya no Hitorigoto - 05', state: 'import_failed' },
            actions: ['retry', 'abandon'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': {
        status: 409,
        body: { detail: { reason: 'low_disk_space', detail: '' } },
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重試' }))

    expect(await within(row).findByText(/剩下的空間低於門檻，所以沒有重試/)).toBeInTheDocument()
  })

  it('一直失敗的 Feed 說出是哪一種、從什麼時候、最後的原因，連到 RSS 頁那一個 Feed（M4 票 130）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            id: 1,
            type: 'feed_poll_failing',
            subject: '3',
            path: '',
            job_hash: '',
            ledger_id: null,
            detail: {
              feed: 3,
              name: 'Mikan',
              error: 'GET https://mikanani.me/RSS/MyBangumi?token=***: connection refused',
              since: '2026-10-20T03:00:00+00:00',
            },
            actions: [],
          }),
          issue({
            id: 2,
            type: 'feed_backfill_failing',
            subject: '3',
            path: '',
            job_hash: '',
            ledger_id: null,
            detail: {
              feed: 3,
              name: 'Mikan',
              error: 'backfill mikan:3600:583: 404',
              since: '2026-10-20T03:00:00+00:00',
            },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const [poll, backfill] = await screen.findAllByRole('article')

    expect(within(poll).getByText('輪詢一直失敗')).toBeInTheDocument()
    expect(within(poll).getByText('這個 Feed 輪詢一直失敗，超過一天了')).toBeInTheDocument()
    await userEvent.click(within(poll).getByRole('heading', { name: 'Mikan' }))
    expect(within(poll).getByText(/connection refused/)).toBeInTheDocument()
    expect(within(poll).getByRole('link', { name: 'Mikan' })).toHaveAttribute('href', '/rss#feed-3')
    expect(within(poll).getByText(/這個 Feed 一直讀不到/)).toBeInTheDocument()

    expect(within(backfill).getByText('補漏一直失敗')).toBeInTheDocument()
    await userEvent.click(within(backfill).getByRole('heading', { name: 'Mikan' }))
    expect(within(backfill).getByText('backfill mikan:3600:583: 404')).toBeInTheDocument()
    expect(within(backfill).getByText(/每日補漏讀不到/)).toBeInTheDocument()
    expect(
      within(backfill)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['忽略'])
  })

  it('缺集列出缺哪幾集，連到作品頁（M4 票 130）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'series_episodes_missing',
            subject: '7',
            path: '',
            job_hash: '',
            ledger_id: null,
            detail: {
              series: 7,
              name: '[LoliHouse] Kimi to Koishitai - 07',
              media: 'tv:120089',
              title: '与你相恋',
              missing: [
                { season: 1, episode: 3 },
                { season: 1, episode: 4 },
                { season: 1, episode: 6 },
              ],
            },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText('缺集')).toBeInTheDocument()
    await userEvent.click(
      within(row).getByRole('heading', { name: '[LoliHouse] Kimi to Koishitai - 07' }),
    )
    expect(within(row).getByText('S01 E03–E04, E06')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: '与你相恋' })).toHaveAttribute(
      'href',
      '/media/tv%3A120089',
    )
    expect(within(row).getByText(/搜這部作品缺的集/)).toBeInTheDocument()
  })

  it('同一集意外多份說出哪一集、撞在一起的發佈名，連到作品頁（M4 票 130）', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'series_episodes_collide',
            subject: '7',
            path: '',
            job_hash: '',
            ledger_id: null,
            detail: {
              series: 7,
              name: '[LoliHouse] Kimi to Koishitai - 06',
              media: 'tv:120089',
              title: '与你相恋',
              collisions: [
                {
                  season: 1,
                  episode: 5,
                  releases: ['[LoliHouse] Kimi - 05 [1080p]', '[LoliHouse] Kimi - 06 [1080p]'],
                },
              ],
            },
            actions: [],
          }),
        ],
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    expect(within(row).getByText('同一集多份')).toBeInTheDocument()
    expect(
      within(row).getByText('這個 RSS Series 有兩個不同的發佈被入庫成同一集'),
    ).toBeInTheDocument()
    await userEvent.click(
      within(row).getByRole('heading', { name: '[LoliHouse] Kimi to Koishitai - 06' }),
    )
    expect(within(row).getByText('撞在同一集 S01E05')).toBeInTheDocument()
    // 一行一個：窄版上分得出第二個從哪裡開始。
    expect(within(row).getByText('[LoliHouse] Kimi - 05 [1080p]')).toHaveClass('block')
    expect(within(row).getByText('[LoliHouse] Kimi - 06 [1080p]')).toHaveClass('block')
    expect(within(row).getByRole('link', { name: '与你相恋' })).toHaveAttribute(
      'href',
      '/media/tv%3A120089',
    )
    expect(within(row).getByText(/指派到正確的集/)).toBeInTheDocument()
  })

  it('重新入庫先選作品，送出去的是選的那一部（M2 票 10）', async () => {
    const FOLDER = '/data/torrent/complete/anime/[Group] SPY×FAMILY S01'
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            subject: FOLDER,
            path: FOLDER,
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['delete_orphan', 'adopt'],
          }),
        ],
      },
      'GET /api/discover/search?q=spy': {
        body: {
          items: [
            {
              id: 'tv:120089',
              tmdb_id: 120089,
              kind: 'tv',
              title: 'SPY×FAMILY 間諜家家酒',
              title_en: 'SPY x FAMILY',
              year: 2022,
              poster_url: '',
              poster_url_en: '',
              tracked: true,
            },
          ],
          problem: null,
          detail: '',
        },
      },
      'POST /api/issues/1/resolve': { body: issue({ status: 'resolved', actions: [] }) },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新入庫' }))
    // 沒選作品時沒有主動作可按：按下去才被拒的按鈕不該畫出來。
    expect(within(row).queryByRole('button', { name: /入庫到/ })).not.toBeInTheDocument()
    await userEvent.type(within(row).getByRole('searchbox'), 'spy')
    await userEvent.click(await within(row).findByRole('button', { name: /SPY×FAMILY 間諜家家酒/ }))
    await userEvent.click(
      within(row).getByRole('button', { name: '入庫到《SPY×FAMILY 間諜家家酒》' }),
    )

    await waitFor(() => expect(sent(stub, 'POST /api/issues/1/resolve')).toBe(1))
    const [, init] = stub.mock.calls.find(([input]) => String(input) === '/api/issues/1/resolve')!
    expect(JSON.parse(String(init?.body))).toEqual({ action: 'adopt', media: 'tv:120089' })
  })

  it('選作品從名字讀出的標題開始，焦點在搜尋框上', async () => {
    const FOLDER = '/data/torrent/complete/anime/[Old] SPY×FAMILY - 04 [1080P][CHT]'
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            subject: FOLDER,
            path: FOLDER,
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['delete_orphan', 'adopt'],
            query: 'SPY×FAMILY',
          }),
        ],
      },
      'GET /api/discover/search?q=SPY%C3%97FAMILY': { body: FOUND },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新入庫' }))

    const search = within(row).getByRole('searchbox')
    expect(search).toHaveValue('SPY×FAMILY')
    expect(search).toHaveFocus()
    // 預填的字本身就搜：管理員多半只要點一下結果。
    expect(
      await within(row).findByRole('button', { name: /SPY×FAMILY 間諜家家酒/ }),
    ).toBeInTheDocument()
  })

  it('選作品的搜尋有防抖：連打一個詞不會每個按鍵都打一次 TMDB', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const FOLDER = '/data/torrent/complete/anime/[Old] Forgotten Batch'
    const stub = render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            subject: FOLDER,
            path: FOLDER,
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['adopt'],
            query: '',
          }),
        ],
      },
      'GET /api/discover/search?q=spy%20x': { body: FOUND },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await user.click(within(row).getByRole('button', { name: '重新入庫' }))
    await user.type(within(row).getByRole('searchbox'), 'spy x')
    await vi.advanceTimersByTimeAsync(500)
    await within(row).findByRole('button', { name: /SPY×FAMILY 間諜家家酒/ })

    expect(stub.mock.calls.filter(([url]) => String(url).includes('/search'))).toHaveLength(1)
    vi.useRealTimers()
  })

  it('認領進帳本配不上時那一列留著，並說出是哪一種配不上', async () => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'unmanaged_library_file',
            job_hash: '',
            ledger_id: null,
            detail: { reason: 'not_berth_naming' },
            actions: ['claim_file'],
          }),
        ],
      },
      'POST /api/issues/1/resolve': {
        status: 409,
        body: { detail: { reason: 'unclaimable', detail: 'no_source' } },
      },
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    // `rebuild-ledger` 開的那一件帶著上一次沒配上的理由。
    await userEvent.click(within(row).getByText('展開'))
    expect(within(row).getByText(/不是 Berth 的命名模板寫得出來的/)).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '認領進帳本' }))

    expect(
      await within(row).findByText(
        /配不上帳本，所以什麼都沒有寫。 complete 裡沒有一個檔案與它是同一份資料/,
      ),
    ).toBeInTheDocument()
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
  it('跑完之後各方都說得出比了幾筆', async () => {
    render({ [RECONCILE]: { body: finished() } })
    renderApp('/issues')

    // 在橫幅裡找，不是整頁：`媒體庫` 也是導覽列上的一個連結。
    const banner = await screen.findByRole('list', { name: '對帳進度' })
    for (const label of ['帳本', 'qBittorrent', 'COMPLETE', '媒體庫', 'Jellyfin'])
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

  // M2 票 16 audit P3（M3 票 06）：上一輪早就跑完了，進頁時不必因為「看到一輪」再問一次清單。
  it('進頁時清單只問一次', async () => {
    const stub = render({ [RECONCILE]: { body: finished() } })
    renderApp('/issues')

    await screen.findByText(/帳本與磁碟對得上/)
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(sent(stub, ISSUES)).toBe(1)
  })

  it('看著的時候跑完一輪，清單重問一次：那一輪開出來的要出現在下面', async () => {
    const stub = render({ [RECONCILE]: { body: finished() } })
    const { queryClient } = renderApp('/issues')
    await screen.findByText(/帳本與磁碟對得上/)

    queryClient.setQueryData(reconcileQueryOptions().queryKey, finished({ id: 2 }))

    await waitFor(() => expect(sent(stub, ISSUES)).toBe(2))
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

// M4 票 89：拒絕原因解析不出來時，原本一律說「Berth 自己的 API 沒有回應」——500 與 401 也是。
describe('待處理頁對 Berth 的請求沒成時說出對的原因', () => {
  it.each(REQUEST_FAILURES)('讀不到清單（%s）', async (_, failure, expected) => {
    render({ [ISSUES]: failure })
    renderApp('/issues')

    const notice = await screen.findByText(/^讀不到待處理清單。/)
    expect(notice).toHaveTextContent(expected)
    expect(notice).not.toHaveTextContent(/自己的 API/)
  })

  it.each(REQUEST_FAILURES)(
    '處理一件（%s）：那一列留著，說出原因',
    async (_, failure, expected) => {
      render({ [ISSUES]: { body: [issue()] }, 'POST /api/issues/1/resolve': failure })
      renderApp('/issues')
      const row = await screen.findByRole('article')

      await userEvent.click(within(row).getByRole('button', { name: '重新鏈接' }))

      const alert = await within(row).findByRole('alert')
      expect(alert).toHaveTextContent(/沒有成功。/)
      expect(alert).toHaveTextContent(expected)
      expect(alert).not.toHaveTextContent(/自己的 API/)
    },
  )

  it.each(REQUEST_FAILURES)('選作品的搜尋（%s）', async (_, failure, expected) => {
    render({
      [ISSUES]: {
        body: [
          issue({
            type: 'orphan_complete',
            job_hash: '',
            ledger_id: null,
            detail: { folder: true },
            actions: ['adopt'],
          }),
        ],
      },
      'GET /api/discover/search?q=spy': failure,
    })
    renderApp('/issues')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '重新入庫' }))
    await userEvent.type(within(row).getByRole('searchbox'), 'spy')

    const said = await within(row).findByText(/^沒有搜成。/)
    expect(said).toHaveTextContent(expected)
  })

  it.each(REQUEST_FAILURES)('立刻對帳（%s）', async (_, failure, expected) => {
    render({ [START]: failure })
    renderApp('/issues')

    await userEvent.click(await screen.findByRole('button', { name: '立刻對帳' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/對帳沒有開始。/)
    expect(alert).toHaveTextContent(expected)
    expect(alert).not.toHaveTextContent(/自己的 API/)
  })
})

/** 這一支端點被送出去幾次。 */
const FOUND = {
  items: [
    {
      id: 'tv:120089',
      tmdb_id: 120089,
      kind: 'tv',
      title: 'SPY×FAMILY 間諜家家酒',
      title_en: 'SPY x FAMILY',
      year: 2022,
      poster_url: '',
      poster_url_en: '',
      tracked: true,
    },
  ],
  problem: null,
  detail: '',
}

function sent(stub: ReturnType<typeof stubApi>, key: string) {
  const [method, path] = key.split(' ')
  return stub.mock.calls.filter(
    ([input, init]) => (init?.method ?? 'GET') === method && String(input) === path,
  ).length
}

describe('通知連結的片段（M4 票 127）', () => {
  it('#issue-2 在資料回來之後捲到那一件、焦點落在它', async () => {
    render({ [ISSUES]: { body: [issue(), issue({ id: 2, path: `${TARGET}.2` })] } })
    const scrolled = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrolled
    onTestFinished(() => {
      Element.prototype.scrollIntoView = original
    })
    renderApp('/issues#issue-2')

    await screen.findAllByRole('article')

    await waitFor(() => expect(document.activeElement?.id).toBe('issue-2'))
    expect(scrolled).toHaveBeenCalledWith({ block: 'center' })
  })

  it('那一件已經處理掉了：不動焦點', async () => {
    render({ [ISSUES]: { body: [issue()] } })
    const scrolled = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrolled
    onTestFinished(() => {
      Element.prototype.scrollIntoView = original
    })
    renderApp('/issues#issue-99')

    await screen.findByRole('article')

    expect(scrolled).not.toHaveBeenCalledWith({ block: 'center' })
    expect(document.body).toHaveFocus()
  })
})

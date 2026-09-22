import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderApp, renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  CHECKS_PASSED,
  indexerSetup,
  jellyfinSetup,
  libraryChoice,
  library,
  routeSetup,
  routeView,
  setupStatus,
  step,
  tmdbSetup,
} from '../test/fixtures'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const ROUTES = 'GET /api/setup/routes'
const BUILD = 'POST /api/setup/routes'
const COMPLETE = 'POST /api/setup/complete'
const ADD_PATH = 'POST /api/setup/jellyfin/libraries/paths'
const INDEXERS = 'GET /api/setup/indexers'
const TMDB = 'GET /api/setup/tmdb'

/** 前三個泊位都接好了，精靈在泊位 4。 */
const AT_BERTH_FOUR = setupStatus({
  current_step: 7,
  admin_created: true,
  admin_username: 'skipper',
  services: ALL_BUNDLED,
})

/** 四個泊位都接好了，剩下按完成。 */
const AT_THE_END = setupStatus({ ...AT_BERTH_FOUR, current_step: 8 })

const BUILT = routeSetup({
  routes: [
    routeView({ library: 'Movies', slug: 'movies', collection_type: 'movies' }),
    routeView({ library: 'TV', slug: 'tv' }),
    routeView({ library: 'Anime', slug: 'anime' }),
  ],
  libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
  ready: true,
})

describe('泊位 4：媒體庫路徑（套件內）', () => {
  it('剖面在按之前就列出將建立的三條 Route 與它們的寫入目標', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: routeSetup() } })

    renderWithProviders(<SetupPage />)
    const plan = (await screen.findByText('將建立')).closest('section')!

    expect(within(plan).getByText('Movies')).toBeInTheDocument()
    expect(within(plan).getByText('/data/library/tv')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '建立 3 條 Route 並檢查' })).toBeInTheDocument()
  })

  it('剖面與按鈕的數字都只算建得了 Route 的媒體庫', async () => {
    const withMusic = routeSetup({
      libraries: [
        ...routeSetup().libraries,
        libraryChoice({ name: '音樂', collection_type: 'music', supported: false }),
      ],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: withMusic } })

    renderWithProviders(<SetupPage />)
    const plan = (await screen.findByText('將建立')).closest('section')!

    expect(within(plan).queryByText('音樂')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '建立 3 條 Route 並檢查' })).toBeInTheDocument()
  })

  it('按下之後每條 Route 逐項顯示檢查結果，含硬鏈接的 inode', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: BUILT },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立 3 條 Route 並檢查' }))

    const sequences = await screen.findAllByTestId('checks')
    expect(sequences).toHaveLength(3)
    expect(within(sequences[1]).getByText('硬鏈接與 inode 比對')).toBeInTheDocument()
    // 實測值留在那一行：這是「三個容器看到同一個檔案系統」唯一的證據。
    expect(
      within(sequences[1]).getByText('dev=70 · inode=8162774324533690 · 137.4 GB free'),
    ).toBeInTheDocument()
    expect(within(sequences[1]).getAllByText('已完成')).toHaveLength(5)
  })

  it('送出的是空的勾選：套件內的三條由伺服器自己導出', async () => {
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { body: BUILT },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立 3 條 Route 並檢查' }))
    await screen.findAllByTestId('checks')

    const call = fetch.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({ selections: [] })
  })

  it('三條都建好之後，剖面不再說「將建立」那三條（票 14、14e 留給票 15 的兩條）', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)
    await screen.findByRole('button', { name: '重新檢查 3 條 Route' })

    expect(screen.queryByText('將建立')).not.toBeInTheDocument()
    const count = screen.getByText('這一輪要建的 Route').closest('div')!
    expect(within(count).getByText('0')).toBeInTheDocument()
  })

  it('三條都建好之後再按一次是全部重驗，不會多建（票 14：精靈只新增）', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '重新檢查 3 條 Route' })).toBeEnabled()
  })

  it('每條 Route 底下都有刪除：二次確認之後打精靈自己的 DELETE，刪完列消失並播報（票 14、14a）', async () => {
    let deleted = false
    const withoutMovies = routeSetup({
      ...BUILT,
      routes: BUILT.routes.filter((route) => route.slug !== 'movies'),
    })
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: () => ({ body: deleted ? withoutMovies : BUILT }),
      'DELETE /api/setup/routes/2': () => {
        deleted = true
        return { status: 204, body: null }
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText('已刪除「Movies」。')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: '刪除這條 Route' })).toHaveLength(2),
    )
    // `/routes/*` 永遠只有 admin；精靈跑完之前沒有人登入得了，所以精靈走 `setup/*` 那一支。
    expect(
      fetch.mock.calls.some(
        ([input, init]) => init?.method === 'DELETE' && String(input) === '/api/setup/routes/2',
      ),
    ).toBe(true)
  })

  it('刪的那一刻被引用：說出數字（票 14a）', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: BUILT },
      'DELETE /api/setup/routes/2': {
        status: 409,
        body: {
          detail: {
            reason: 'route_in_use',
            detail: 'jobs=1 · ledger_entries=0',
            jobs: 1,
            ledger_entries: 0,
          },
        },
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText(/刪不得/)).toHaveTextContent('1 筆下載、0 個入庫檔案')
  })

  it('409 沒帶數字時仍說刪不得，不說後端沒在跑', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: BUILT },
      'DELETE /api/setup/routes/2': {
        status: 409,
        body: { detail: { reason: 'route_in_use', detail: 'jobs=1 · ledger_entries=0' } },
      },
    })

    renderWithProviders(<SetupPage />)
    const [first] = await screen.findAllByRole('button', { name: '刪除這條 Route' })
    await userEvent.click(first)
    await userEvent.click(screen.getByRole('button', { name: '確定刪除' }))

    expect(await screen.findByText(/刪不得/)).toBeInTheDocument()
    expect(screen.queryByText(/沒在跑/)).not.toBeInTheDocument()
  })

  it('停用中的紅燈 Route 不讓第四格變紅：它不是目的地，完成條件也不算它（票 14）', async () => {
    const withDisabledRed = routeSetup({
      ...BUILT,
      routes: [
        ...BUILT.routes,
        routeView({ id: 9, library: 'TV', slug: 'tv-2', enabled: false, health: 'failed' }),
      ],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: withDisabledRed } })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 4').closest('li')).toHaveTextContent('已完成'),
    )
  })

  it('泊位板的第四格全綠之後標成已繫上', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: BUILT } })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 4').closest('li')).toHaveTextContent('已完成'),
    )
  })
})

describe('泊位 4 的失敗', () => {
  it('EXDEV 指出兩個目錄是不同掛載，並附三個容器的 compose 片段', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          cross_device: true,
          checks: [
            ...CHECKS_PASSED.slice(0, 4),
            step('hardlink', 'failed', '', '[Errno 18] Invalid cross-device link'),
          ],
        }),
      ],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('[Errno 18] Invalid cross-device link')).toBeInTheDocument()
    expect(screen.getByText(/EXDEV/)).toBeInTheDocument()
    expect(screen.getByText(/berth:\s+volumes:/)).toBeInTheDocument()
  })

  it('Jellyfin 看不到探測檔時說的是 jellyfin 少了掛載', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          checks: [
            ...CHECKS_PASSED.slice(0, 3),
            step('probe_visible', 'failed', '', 'Jellyfin cannot see /data/library/tv'),
            step('hardlink', 'pending'),
          ],
        }),
      ],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('Jellyfin cannot see /data/library/tv')).toBeInTheDocument()
    expect(screen.getByText(/jellyfin 容器少了這條路徑的掛載/)).toBeInTheDocument()
  })

  it('category 已存在但路徑不同時說明不覆寫的理由', async () => {
    const blocked = routeSetup({
      routes: [
        routeView({
          library: 'TV',
          health: 'failed',
          checks: [
            step('category', 'failed', '', "category 'berth-tv' already points at '/mnt/old/tv'"),
            ...CHECKS_PASSED.slice(1).map((row) => step(row.step, 'pending')),
          ],
        }),
      ],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: blocked } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/already points at/)).toBeInTheDocument()
    expect(screen.getByText(/autoTMM/)).toBeInTheDocument()
  })

  /**
   * 票 02a。這一步順帶重跑既有 Route 的檢查，途中被另一個分頁刪掉的那一條是 404
   * `route_missing`（票 01）。原本這裡只吃 `build.isError`，畫面因此說「後端可能沒在跑」
   * ——既不是原因也不是下一步（PRODUCT 原則 4）。
   */
  it('建立途中有 Route 被刪掉：說出是哪一種失敗與下一步，不說後端沒在跑', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: {
        status: 404,
        body: { detail: { reason: 'route_missing', detail: '2' } },
      },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立 3 條 Route 並檢查' }))

    const notice = await screen.findByText(/被刪掉了/)
    expect(notice).toHaveTextContent('重新檢查了既有的 Route')
    expect(notice).toHaveTextContent('重新整理這一步')
    expect(screen.queryByText(/後端可能沒在跑/)).not.toBeInTheDocument()
  })

  it('認不得的失敗仍落回那句通用的話：只有說得出原因時才換掉它', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: routeSetup() },
      [BUILD]: { status: 500, body: { detail: 'boom' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '建立 3 條 Route 並檢查' }))

    expect(await screen.findByText(/後端可能沒在跑/)).toBeInTheDocument()
    expect(screen.queryByText(/被刪掉了/)).not.toBeInTheDocument()
  })
})

describe('泊位 4：媒體庫路徑（既有 Jellyfin）', () => {
  const NAS = routeSetup({
    origin: 'existing',
    libraries: [
      libraryChoice({
        name: '影集',
        locations: ['/volume1/media/tv', '/data/library/影集'],
        berth_path: '/data/library/影集',
        target_path: '',
      }),
      libraryChoice({ name: '音樂', collection_type: 'music', supported: false, locations: [] }),
    ],
  })

  it('一個都沒勾時建立鍵按不下去', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: NAS } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '建立 0 條 Route 並檢查' })).toBeDisabled()
  })

  it('勾了媒體庫再選一條路徑，送出去的就是那一條', async () => {
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: NAS },
      [BUILD]: { body: NAS },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))
    await userEvent.click(screen.getByRole('radio', { name: '/data/library/影集' }))
    await userEvent.click(screen.getByRole('button', { name: '建立 1 條 Route 並檢查' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({
        selections: [{ library: '影集', target_path: '/data/library/影集' }],
      })
    })
  })

  it('不是電影或劇集的媒體庫不給勾，並說明理由', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: NAS } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('音樂')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: '音樂' })).not.toBeInTheDocument()
    expect(screen.getByText(/只寫入電影與劇集/)).toBeInTheDocument()
  })

  it('還沒有 Berth 路徑的媒體庫可以就地加一條', async () => {
    const withoutBerthPath = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({
          name: '影集',
          locations: ['/volume1/media/tv'],
          berth_path: '/data/library/影集',
          has_berth_path: false,
          target_path: '/volume1/media/tv',
        }),
      ],
    })
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: withoutBerthPath },
      [ADD_PATH]: { body: jellyfinSetup({ libraries: [library()] }) },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))
    await userEvent.click(screen.getByRole('button', { name: '加入 Berth 路徑' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(
        ([input, init]) => init?.method === 'POST' && String(input).endsWith('/libraries/paths'),
      )
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]?.body))).toEqual({ library: '影集' })
    })
  })

  /**
   * 票 03 第 6 條。已經被佔用的路徑本來得按下「建立並檢查」被後端退回來（422）才知道，
   * 而那時候畫面只說得出「請求沒有走完」。`/settings/routes` 的新增表早就是這樣做的。
   */
  it('已經被別條 Route 佔用的路徑在勾選表上就標出來，選不了', async () => {
    const shared = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({
          name: '影集',
          locations: ['/volume1/media/tv', '/data/library/影集'],
          target_path: '',
        }),
      ],
      routes: [routeView({ name: '舊影集', library: '別的庫', target_path: '/volume1/media/tv' })],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: shared } })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))

    const taken = screen.getByRole('radio', { name: /\/volume1\/media\/tv/ })
    expect(taken).toBeDisabled()
    // 佔著它的那條 Route 的名字就在那一行上，而且掛進了這顆 radio 的可存取描述。
    expect(taken).toHaveAccessibleDescription('已是「舊影集」')
    // 沒被佔的那一條照樣選得起來。
    expect(screen.getByRole('radio', { name: /\/data\/library\/影集/ })).toBeEnabled()
  })

  it('已經有 Route 的媒體庫在勾選表上鎖住：重跑不改也不刪它（票 14）', async () => {
    const routed = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({ name: '影集', has_route: true, target_path: '/data/library/影集' }),
      ],
      routes: [routeView({ library: '影集', slug: '影集', target_path: '/data/library/影集' })],
    })
    stubApi({ [STATUS]: { body: AT_BERTH_FOUR }, [ROUTES]: { body: routed } })

    renderWithProviders(<SetupPage />)

    const box = await screen.findByRole('checkbox', { name: '影集' })
    expect(box).toBeChecked()
    expect(box).toBeDisabled()
    expect(screen.getByText(/精靈只新增/)).toBeInTheDocument()
    // 沒有新勾的東西時，這一顆是「全部重驗」而不是一顆按不下去的建立鍵。
    expect(screen.getByRole('button', { name: '重新檢查 1 條 Route' })).toBeEnabled()
  })
})

describe('第 8 步：完成', () => {
  it('列出跑出來的 Route 與跳過的索引站、在哪裡補', async () => {
    stubApi({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup({ skipped: true }) },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('button', { name: '完成設定' })).toBeInTheDocument()
    expect(screen.getByText('/data/torrent/complete/tv')).toBeInTheDocument()
    expect(screen.getByText(/索引站還沒接/)).toBeInTheDocument()
  })

  /**
   * 票 03 第 5 條。後端的 422 是「不可跳的那幾步還沒做完」（`services/setup.py` 的兩個
   * `ValueError`），不是後端掛了——原本兩種都說「Berth 後端可能沒在跑」，把使用者送去看容器。
   */
  it('缺 TMDB 憑證時說的是第 6 步沒做完，不是後端出錯', async () => {
    stubApi({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: false, verified: false }) },
      [COMPLETE]: { status: 422, body: { detail: 'finish step 6 first: TMDB needs a credential' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/TMDB/)
    expect(alert).not.toHaveTextContent(/後端/)
    // 修的地方在第 6 步，所以出口也在這裡。
    expect(screen.getByRole('button', { name: /TMDB/ })).toBeInTheDocument()
  })

  /**
   * 票 03 code review：`tmdb.verified` 還沒載回來時原本會一律說「第 6 步」，
   * 即使真正卡住的是第 7 步。兩份狀態都說沒問題卻仍被擋，就別指名。
   */
  it('422 但手上這份看不出是哪一步時，不硬指一步也不怪後端', async () => {
    stubApi({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: true, verified: true }) },
      [COMPLETE]: { status: 422, body: { detail: 'some newer precondition' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/看不出是哪一步/)
    expect(alert).not.toHaveTextContent(/後端/)
    expect(screen.queryByRole('button', { name: /TMDB/ })).not.toBeInTheDocument()
  })

  it('後端真的掛了時才說是後端', async () => {
    stubApi({
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ api_key_present: true, verified: true }) },
      [COMPLETE]: { status: 500, body: { detail: 'boom' } },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/後端/)
  })

  it('按下完成之後精靈關閉，回首頁時不再被導回精靈', async () => {
    let completed = false
    stubApi({
      'GET /api/health': () => ({
        body: { status: 'ok', version: '0.1.0', setup_completed: completed },
      }),
      [STATUS]: { body: AT_THE_END },
      [ROUTES]: { body: BUILT },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [COMPLETE]: () => {
        completed = true
        return { body: { ...AT_THE_END, completed: true } }
      },
      'GET /api/auth/me': { status: 401, body: { detail: 'sign in to use this API' } },
    })

    const { router } = renderApp('/setup')
    await userEvent.click(await screen.findByRole('button', { name: '完成設定' }))

    // 精靈跑完之後 `/` 不再導向 `/setup`，而是導向登入頁（票 07 的守衛）。
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })
})

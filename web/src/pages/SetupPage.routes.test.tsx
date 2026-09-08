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
} from '../test/setupStatus'
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
    routeView({ library: 'Anime', slug: 'anime', profile: 'anime' }),
  ],
  libraries: routeSetup().libraries.map((row) => ({ ...row, selected: true })),
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
        selections: [{ library: '影集', target_path: '/data/library/影集', profile: 'standard' }],
      })
    })
  })

  it('兩個劇集媒體庫各有自己的 profile，選一個不會清掉另一個', async () => {
    const two = routeSetup({
      origin: 'existing',
      libraries: [
        libraryChoice({ name: '影集', target_path: '/data/library/影集' }),
        libraryChoice({ name: '動畫', target_path: '/data/library/動畫' }),
      ],
    })
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: two },
      [BUILD]: { body: two },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))
    await userEvent.click(screen.getByRole('checkbox', { name: '動畫' }))
    const [firstAnime, secondAnime] = screen.getAllByRole('radio', { name: '動漫' })
    // 原生 radio 群組是靠 `name` 分的：兩個媒體庫共用一個名字，方向鍵就會在它們之間跳，
    // 螢幕閱讀器也會把兩組唸成同一組。
    expect(firstAnime.getAttribute('name')).not.toBe(secondAnime.getAttribute('name'))
    await userEvent.click(firstAnime)
    await userEvent.click(secondAnime)
    await userEvent.click(screen.getByRole('button', { name: '建立 2 條 Route 並檢查' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
      const profiles = JSON.parse(String(call![1]?.body)).selections.map(
        (row: { profile: string }) => row.profile,
      )
      // 兩組 radio 各自獨立：後選的那個沒有把前一個彈回標準。
      expect(profiles).toEqual(['anime', 'anime'])
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

  it('劇集媒體庫可以挑動漫 profile', async () => {
    const fetch = stubApi({
      [STATUS]: { body: AT_BERTH_FOUR },
      [ROUTES]: { body: NAS },
      [BUILD]: { body: NAS },
    })

    renderWithProviders(<SetupPage />)
    await userEvent.click(await screen.findByRole('checkbox', { name: '影集' }))
    await userEvent.click(screen.getByRole('radio', { name: '/volume1/media/tv' }))
    await userEvent.click(screen.getByRole('radio', { name: '動漫' }))
    await userEvent.click(screen.getByRole('button', { name: '建立 1 條 Route 並檢查' }))

    await waitFor(() => {
      const call = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
      expect(JSON.parse(String(call![1]?.body)).selections[0].profile).toBe('anime')
    })
  })
})

describe('第 8 步：完成', () => {
  it('列出跑出來的 Route 與跳過了什麼、在哪裡補', async () => {
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
    expect(screen.queryByText(/TMDB 還沒驗證/)).not.toBeInTheDocument()
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

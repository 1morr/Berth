import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  SEQUENCE_DONE,
  detection,
  jellyfinSetup,
  library,
  setupStatus,
  step,
} from '../test/setupStatus'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const JELLYFIN = 'GET /api/setup/jellyfin'
const BOOTSTRAP = 'POST /api/setup/jellyfin/bootstrap'
const CONNECT = 'POST /api/setup/jellyfin/connect'
const PATHS = 'POST /api/setup/jellyfin/libraries/paths'
const PLUGIN = 'POST /api/setup/jellyfin/plugin'

/** 第 1–2 步都做完了，精靈在泊位 1。 */
const AT_BERTH_ONE = setupStatus({
  current_step: 3,
  admin_created: true,
  admin_username: 'skipper',
  services: ALL_BUNDLED,
})

const NAS = setupStatus({
  ...AT_BERTH_ONE,
  services: [
    detection({ origin: 'existing', reason: 'setup_completed', detail: '10.10.7' }),
    ...ALL_BUNDLED.slice(1),
  ],
})

describe('泊位 1：套件內 Jellyfin', () => {
  it('剖面在按之前就列出九支端點', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_ONE }, [JELLYFIN]: { body: jellyfinSetup() } })

    renderWithProviders(<SetupPage />)
    // 剖面是那份 `dl`；序列裡的每一條纜繩也標著自己的端點，所以要限定在剖面內找。
    const cutaway = (await screen.findByText('將會做什麼')).closest('section')!

    expect(within(cutaway).getByText('POST /Startup/User')).toBeInTheDocument()
    expect(within(cutaway).getByText('POST /Library/VirtualFolders')).toBeInTheDocument()
    expect(within(cutaway).getByText('POST /Auth/Keys')).toBeInTheDocument()
    expect(within(cutaway).getByText('GET /ScheduledTasks')).toBeInTheDocument()
    expect(within(cutaway).getByText('建立 Movies / TV / Anime 三個媒體庫')).toBeInTheDocument()
  })

  it('按下靠泊之後逐條纜繩留下實測值', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: { body: jellyfinSetup() },
      [BOOTSTRAP]: { body: jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始靠泊' }))

    const sequence = await screen.findByTestId('sequence')
    await waitFor(() => expect(within(sequence).getAllByText('已完成')).toHaveLength(9))
    expect(within(sequence).getByText('Movies · TV · Anime')).toBeInTheDocument()
    expect(within(sequence).getByText('fd957c84 · dcaf151d')).toBeInTheDocument()
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/bootstrap')).toBe(true)
  })

  it('重按之後已經對的那幾步標成「已經是這樣」', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          api_key_present: true,
          steps: [
            step('public_info', 'ok', '10.11.11'),
            ...SEQUENCE_DONE.slice(1).map((row) => ({ ...row, status: 'skipped' as const })),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)
    const sequence = await screen.findByTestId('sequence')

    await waitFor(() => expect(within(sequence).getAllByText('已經是這樣')).toHaveLength(8))
    expect(screen.getByRole('button', { name: '重新跑一次' })).toBeInTheDocument()
  })

  it('失敗的那一步就地變紅，附原文與可複製的手動步驟', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_ONE },
      [JELLYFIN]: {
        body: jellyfinSetup({
          api_key_present: true,
          steps: [
            ...SEQUENCE_DONE.slice(0, 7),
            step('plugin', 'failed', '', 'MergeVersions did not install after 3 tries: 500'),
            step('tasks', 'pending'),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/MergeVersions did not install/)).toBeInTheDocument()
    expect(
      screen.getByText(
        'https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重試失敗的那一步' })).toBeInTheDocument()
    const sequence = screen.getByTestId('sequence')
    expect(within(sequence).getByText('尚未執行')).toBeInTheDocument()
  })

  it('泊位板在精靈前進之後把 BTH 1 標成已繫上', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ ...AT_BERTH_ONE, current_step: 4 }) },
      [JELLYFIN]: { body: jellyfinSetup({ steps: SEQUENCE_DONE, api_key_present: true }) },
    })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() =>
      expect(within(board).getByText('BTH 1').closest('li')).toHaveClass('bg-secured'),
    )
  })
})

describe('泊位 1：既有 Jellyfin', () => {
  const CONNECTED = jellyfinSetup({
    origin: 'existing',
    base_url: 'http://nas:8096',
    api_key_present: true,
    steps: [step('public_info', 'ok', '10.10.7'), step('api_key', 'ok', 'Berth')],
    libraries: [
      library(),
      library({
        name: 'Anime',
        collection_type: 'tvshows',
        locations: ['/volume1/media/anime'],
        metadata_fetchers: ['TheTVDB', 'TheMovieDb'],
        uses_tvdb: true,
        berth_path: '/data/library/anime',
      }),
    ],
  })

  it('先要那台伺服器的管理員帳密，沒有靠泊按鈕', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096' }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByLabelText('Jellyfin 管理員帳號')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '開始靠泊' })).not.toBeInTheDocument()
    // 紅線：既有 Jellyfin 上不會出現任何「建立媒體庫」的動作。
    expect(screen.queryByText(/建立 Movies/)).not.toBeInTheDocument()
  })

  it('送出帳密去換一把 API key', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: jellyfinSetup({ origin: 'existing', base_url: 'http://nas:8096' }) },
      [CONNECT]: { body: CONNECTED },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('Jellyfin 管理員帳號'), 'owner')
    await user.type(screen.getByLabelText('Jellyfin 管理員密碼'), 's3cret')
    await user.click(screen.getByRole('button', { name: '登入並建立 API key' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/jellyfin/connect')
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({
        username: 'owner',
        password: 's3cret',
      })
    })
  })

  it('列出媒體庫與各自路徑，掛 TVDB 的那個給警告', async () => {
    stubApi({ [STATUS]: { body: NAS }, [JELLYFIN]: { body: CONNECTED } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('/volume1/media/films')).toBeInTheDocument()
    expect(screen.getByText('/volume1/media/anime')).toBeInTheDocument()
    expect(screen.getByText('TheTVDB · TheMovieDb')).toBeInTheDocument()
    expect(screen.getByText(/這個媒體庫用 TVDB 取 metadata/)).toBeInTheDocument()
  })

  it('「加入 Berth 路徑」要二次確認才送出，並先顯示會加哪一條', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [PATHS]: { body: CONNECTED },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const films = (await screen.findByText('Films')).closest('li')!
    expect(within(films).getByText('/data/library/films')).toBeInTheDocument()

    await user.click(within(films).getByRole('button', { name: '加入 Berth 路徑' }))

    // 還沒送出，先說清楚舊路徑不動。
    expect(
      fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/libraries/paths'),
    ).toBe(false)
    expect(within(films).getByText(/舊路徑不動/)).toBeInTheDocument()

    await user.click(within(films).getByRole('button', { name: '確認加入' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(
        ([url]) => url === '/api/setup/jellyfin/libraries/paths',
      )
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({ library: 'Films' })
    })
  })

  it('已經有 Berth 路徑的媒體庫不再顯示那顆按鈕', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: {
        body: {
          ...CONNECTED,
          libraries: [
            library({
              locations: ['/volume1/media/films', '/data/library/films'],
              has_berth_path: true,
            }),
          ],
        },
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('已接上')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加入 Berth 路徑' })).not.toBeInTheDocument()
  })

  it('「安裝 MergeVersions」要二次確認並說明會重啟 Jellyfin', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: CONNECTED },
      [PLUGIN]: { body: { ...CONNECTED, merge_versions_installed: true } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '安裝 MergeVersions' }))

    expect(screen.getByText(/重啟 Jellyfin/)).toBeInTheDocument()
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/plugin')).toBe(false)

    await user.click(screen.getByRole('button', { name: '確認安裝並重啟' }))

    await waitFor(() =>
      expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/jellyfin/plugin')).toBe(true),
    )
  })

  it('加路徑失敗時就地顯示原文與手動步驟', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: {
        body: {
          ...CONNECTED,
          steps: [
            ...CONNECTED.steps,
            step('libraries', 'failed', 'Films', 'POST /Library/VirtualFolders/Paths: 404'),
          ],
        },
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('POST /Library/VirtualFolders/Paths: 404')).toBeInTheDocument()
    expect(screen.getByText(/同一個宿主目錄掛在同一個容器路徑/)).toBeInTheDocument()
    expect(screen.getByText('http://nas:8096/web/#/dashboard/libraries')).toBeInTheDocument()
  })

  it('一個媒體庫都沒有時說清楚下一步', async () => {
    stubApi({
      [STATUS]: { body: NAS },
      [JELLYFIN]: { body: { ...CONNECTED, libraries: [] } },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('沒有媒體庫')).toBeInTheDocument()
    expect(screen.getByText(/先在 Jellyfin 建一個媒體庫再回來/)).toBeInTheDocument()
  })
})

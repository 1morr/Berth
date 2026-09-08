import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import {
  ALL_BUNDLED,
  detection,
  indexerSetup,
  qbittorrentSetup,
  setupStatus,
  step,
  tmdbSetup,
} from '../test/setupStatus'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const DIFF = 'GET /api/setup/qbittorrent/diff'
const APPLY = 'POST /api/setup/qbittorrent/apply'
const INDEXERS = 'GET /api/setup/indexers'
const ADD_INDEXERS = 'POST /api/setup/indexers/apply'
const CONNECT_INDEXER = 'POST /api/setup/indexers/connect'
const SKIP_INDEXERS = 'POST /api/setup/indexers/skip'
const TMDB = 'GET /api/setup/tmdb'
const TEST_TMDB = 'POST /api/setup/tmdb/test'

/** 前兩個泊位都接好了，精靈在泊位 2。 */
const AT_BERTH_TWO = setupStatus({
  current_step: 4,
  admin_created: true,
  admin_username: 'skipper',
  services: ALL_BUNDLED,
})

/** 泊位 2 也接好了，精靈在泊位 3。 */
const AT_BERTH_THREE = setupStatus({ ...AT_BERTH_TWO, current_step: 5 })

describe('泊位 2：qBittorrent', () => {
  it('剖面在按之前就逐鍵列出現值與建議值', async () => {
    stubApi({ [STATUS]: { body: AT_BERTH_TWO }, [DIFF]: { body: qbittorrentSetup() } })

    renderWithProviders(<SetupPage />)
    const diff = (await screen.findByText('將會寫入的鍵')).closest('section')!

    expect(within(diff).getByText('temp_path_enabled')).toBeInTheDocument()
    expect(within(diff).getByText('/data/torrent/incomplete')).toBeInTheDocument()
    // 現值也在同一列，使用者看得出來按下去會改掉什麼。
    expect(within(diff).getByText('/downloads/incomplete')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '套用這 5 個鍵' })).toBeInTheDocument()
  })

  it('套用之後逐鍵留下結果，已經是建議值的那幾條標成已經是這樣', async () => {
    const applied = qbittorrentSetup({
      diffs: qbittorrentSetup().diffs.map((row) => ({
        ...row,
        current: row.recommended,
        differs: false,
      })),
      steps: [
        step('temp_path_enabled', 'ok', 'true'),
        step('temp_path', 'ok', '/data/torrent/incomplete'),
        step('save_path', 'skipped', '/data/torrent/complete'),
        step('auto_tmm_enabled', 'ok', 'true'),
        step('category_changed_tmm_enabled', 'ok', 'true'),
        step('web_ui_password', 'ok', 'skipper'),
      ],
    })
    stubApi({
      [STATUS]: { body: AT_BERTH_TWO },
      [DIFF]: { body: qbittorrentSetup() },
      [APPLY]: { body: applied },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '套用這 5 個鍵' }))

    const sequence = await screen.findByTestId('sequence')
    await waitFor(() => {
      expect(within(sequence).getAllByText('已完成')).toHaveLength(5)
    })
    expect(within(sequence).getByText('已經是這樣')).toBeInTheDocument()
    expect(within(sequence).getByText('WebUI 帳密')).toBeInTheDocument()
  })

  it('版本太舊時給的是升級指令，不是一顆按不動的按鈕', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_TWO },
      [DIFF]: {
        body: qbittorrentSetup({
          version: 'v4.3.9',
          webapi_version: '2.8.2',
          supported: false,
          blocked: true,
          diffs: [],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/Web API 低於 2\.8\.4/)).toBeInTheDocument()
    expect(screen.getByText('docker compose pull qbittorrent')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /套用/ })).not.toBeInTheDocument()
  })

  it('既有服務的 temp path 未啟用只是警告，按鈕照樣按得下去', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_TWO },
      [DIFF]: {
        body: qbittorrentSetup({
          origin: 'existing',
          base_url: 'http://nas:8080',
          temp_path_warning: true,
          sets_password: false,
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/沒有啟用未完成目錄/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '套用這 5 個鍵' })).toBeEnabled()
  })

  it('連不上時說得出下一步', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_TWO },
      [DIFF]: {
        body: qbittorrentSetup({
          reachable: false,
          blocked: true,
          supported: false,
          version: '',
          webapi_version: '',
          diffs: [],
          error: 'connection refused',
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('connection refused')).toBeInTheDocument()
    expect(screen.getByText('docker compose logs --tail 50 qbittorrent')).toBeInTheDocument()
  })
})

describe('泊位 3：來源', () => {
  it('十個預設站預設全勾，按鈕說得出會加幾個', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage />)

    const picks = (await screen.findByText('要加入哪些站')).closest('fieldset')!
    const boxes = within(picks).getAllByRole('checkbox')
    expect(boxes).toHaveLength(10)
    expect(boxes.every((box) => (box as HTMLInputElement).checked)).toBe(true)
    expect(screen.getByRole('button', { name: '加入這 10 個站' })).toBeInTheDocument()
  })

  it('取消勾選的站不會被送出去', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [ADD_INDEXERS]: { body: indexerSetup({ steps: [step('nyaasi', 'ok')] }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const picks = (await screen.findByText('要加入哪些站')).closest('fieldset')!
    await user.click(within(picks).getByLabelText('The Pirate Bay'))
    await user.click(screen.getByRole('button', { name: '加入這 9 個站' }))

    const call = fetchStub.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(call[1]?.body)).indexers).not.toContain('thepiratebay')
    expect(JSON.parse(String(call[1]?.body)).indexers).toContain('nyaasi')
  })

  it('逐站顯示成敗：連不上的變紅並展開手動步驟，其餘照樣繫上', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: {
        body: indexerSetup({
          steps: [
            step('nyaasi', 'ok'),
            step(
              '1337x',
              'failed',
              '',
              'Unable to access 1337x.to, blocked by CloudFlare Protection.',
            ),
          ],
        }),
      },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage />)

    const sites = await screen.findByTestId('sites')
    expect(within(sites).getByText('已完成')).toBeInTheDocument()
    expect(within(sites).getByText('失敗')).toBeInTheDocument()
    expect(
      within(sites).getByText('Unable to access 1337x.to, blocked by CloudFlare Protection.'),
    ).toBeInTheDocument()
    expect(within(sites).getByText('http://prowlarr:9696/#/indexers')).toBeInTheDocument()
  })

  it('既有路徑可以填任意 Torznab 端點', async () => {
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({
          ...AT_BERTH_THREE,
          services: [
            ...ALL_BUNDLED.slice(0, 2),
            detection({
              kind: 'prowlarr',
              origin: 'existing',
              reason: 'has_indexers',
              detail: '3',
              base_url: 'http://nas:9696',
            }),
          ],
        }),
      },
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', base_url: '', options: [] }) },
      [TMDB]: { body: tmdbSetup() },
      [CONNECT_INDEXER]: {
        body: indexerSetup({
          origin: 'existing',
          kind: 'torznab',
          base_url: 'http://jackett:9117/api',
          steps: [step('torznab', 'ok', 'Jackett · TV')],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('radio', { name: 'Torznab 端點' }))
    await user.type(screen.getByLabelText('位址'), 'http://jackett:9117/api')
    await user.type(screen.getByLabelText('API key'), 'the-key')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    const call = fetchStub.mock.calls.find(([url]) => String(url).endsWith('/indexers/connect'))!
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      api_key: 'the-key',
    })
    expect(await screen.findByText('Jackett · TV')).toBeInTheDocument()
  })

  it('索引站與 TMDB 都可以之後再說', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [SKIP_INDEXERS]: { body: indexerSetup({ skipped: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const [skipIndexers] = await screen.findAllByRole('button', { name: '之後再說' })
    await user.click(skipIndexers)

    await waitFor(() => {
      expect(fetchStub.mock.calls.some(([url]) => String(url).endsWith('/indexers/skip'))).toBe(
        true,
      )
    })
  })

  it('TMDB 什麼都不填也測得了，測完留下 TMDB 自己報的值', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [TEST_TMDB]: {
        body: tmdbSetup({ steps: [step('configuration', 'ok', 'https://image.tmdb.org/t/p/')] }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試 TMDB' }))

    expect(await screen.findByText('https://image.tmdb.org/t/p/')).toBeInTheDocument()
    const call = fetchStub.mock.calls.find(([url]) => String(url).endsWith('/tmdb/test'))!
    expect(JSON.parse(String(call[1]?.body))).toEqual({ api_key: '' })
  })

  it('填了自己的 key 之後畫面說清楚內建的那把不再被用', async () => {
    stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup({ using_project_credential: false }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/不再用內建的/)).toBeInTheDocument()
  })
})

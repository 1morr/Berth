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
} from '../test/fixtures'
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

describe('設定跑完之後再進來', () => {
  it('深連結 ?berth=2 直接停在 qBittorrent 那一步，而不是從第 1 步重走', async () => {
    // 設定頁的「改位址或憑證」以前三張卡片都連到裸 `/setup`，於是不管按哪一張都落在
    // 第 3 步「接手這台 Jellyfin」（票 11 的 critique，P0）。
    stubApi({
      [STATUS]: {
        body: setupStatus({ current_step: 8, admin_created: true, services: ALL_BUNDLED }),
      },
      [DIFF]: { body: qbittorrentSetup() },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
    })

    renderWithProviders(<SetupPage berth={2} />)

    expect(
      await screen.findByRole('heading', { name: '套用建議的 qBittorrent 設定' }),
    ).toBeVisible()
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

  it('索引站可以之後再說，而且跳過之後畫面上看得出來', async () => {
    // 這一條原本只驗「請求送出去了」，於是「送出去了但畫面沒變」一直沒被抓到：
    // TMDB 那一節有徽章，索引站那一節沒有，按了像壞掉（票 11 的 critique）。
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [SKIP_INDEXERS]: { body: indexerSetup({ skipped: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    expect(screen.queryByTestId('indexers-deferred')).not.toBeInTheDocument()

    // TMDB 那一節沒有「之後再說」——第 6 步是閘門（票 02b），所以這顆按鈕只有一個。
    const skipButtons = await screen.findAllByRole('button', { name: '之後再說' })
    expect(skipButtons).toHaveLength(1)
    await user.click(skipButtons[0])

    await waitFor(() => {
      expect(fetchStub.mock.calls.some(([url]) => String(url).endsWith('/indexers/skip'))).toBe(
        true,
      )
    })
    expect(await screen.findByTestId('indexers-deferred')).toBeInTheDocument()
  })

  it('沒填 key 就按下去會被欄位擋住，畫面說得出去哪裡拿一把', async () => {
    // 第 6 步是閘門（票 02b）：第一次來的人手上還沒有 key，所以畫面要先說去哪裡申請。
    // 按鈕**不停用**——票 11 的 critique 抓過「按不動的控制項讀起來像壞掉」。
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/設定 → API/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '開啟 TMDB 的 API 設定' })).toHaveAttribute(
      'href',
      'https://www.themoviedb.org/settings/api',
    )
    expect(screen.getByTestId('tmdb-required')).toHaveTextContent('必填')

    await user.click(await screen.findByRole('button', { name: '測試 TMDB' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/要一把 key/)
    expect(fetchStub.mock.calls.some(([url]) => String(url).endsWith('/tmdb/test'))).toBe(false)
  })

  it('憑證測不過時，就地給得出兩條跑得動的下一步', async () => {
    // 「key 打錯了」與「連不到 api.themoviedb.org」是兩件事，畫面要兩條都給
    // （PRODUCT.md 原則 4；image 裡沒有 curl，所以連線那條走 python）。
    stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: {
        body: tmdbSetup({
          api_key_present: true,
          steps: [step('configuration', 'failed', '', 'GET /configuration: 401')],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('GET /configuration: 401')).toBeInTheDocument()
    expect(screen.getAllByText('https://www.themoviedb.org/settings/api')).toHaveLength(2)
    expect(
      screen.getByText(/socket\.create_connection\(\('api\.themoviedb\.org', 443\)/),
    ).toBeInTheDocument()
  })

  it('貼上自己的 key 測過之後，留下 TMDB 自己報的值', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_BERTH_THREE },
      [INDEXERS]: { body: indexerSetup() },
      [TMDB]: { body: tmdbSetup() },
      [TEST_TMDB]: {
        body: tmdbSetup({
          api_key_present: true,
          verified: true,
          steps: [step('configuration', 'ok', 'https://image.tmdb.org/t/p/')],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(
      await screen.findByLabelText('你的 TMDB API key'),
      ' 00000000000000000000000000000003 ',
    )
    await user.click(screen.getByRole('button', { name: '測試 TMDB' }))

    expect(await screen.findByText('https://image.tmdb.org/t/p/')).toBeInTheDocument()
    const call = fetchStub.mock.calls.find(([url]) => String(url).endsWith('/tmdb/test'))!
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      api_key: '00000000000000000000000000000003',
    })
    // 綠燈之後那塊「去哪裡拿」就收起來，剖面改說憑證已經在手上。
    expect(screen.queryByText(/設定 → API/)).not.toBeInTheDocument()
    expect(screen.getByTestId('tmdb-required')).toHaveTextContent('已完成')
  })
})

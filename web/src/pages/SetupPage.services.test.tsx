import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import type { SiteSearch } from '../api/setup'
import {
  ALL_BUNDLED,
  DEFAULT_OPTIONS,
  added,
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
const SEARCH = 'GET /api/setup/indexers/search'
const REMOVE_YTS = 'DELETE /api/setup/indexers/3'
const TMDB = 'GET /api/setup/tmdb'
const TEST_TMDB = 'POST /api/setup/tmdb/test'

/** 前兩個泊位都接好了，精靈在泊位 2。 */
const AT_BERTH_TWO = setupStatus({
  current_step: 4,
  admin_created: true,
  admin_username: 'skipper',
  services: ALL_BUNDLED,
})

/** 媒體庫路徑也接好了，精靈在索引站（第 6 步，泊位 4）。 */
const AT_INDEXER = setupStatus({ ...AT_BERTH_TWO, current_step: 6 })

/** 同一步，但 Prowlarr 是使用者自己的那一台。 */
const AT_EXISTING_INDEXER = setupStatus({
  ...AT_INDEXER,
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
})

/** 索引站有結論了，精靈在 TMDB（第 7 步，泊位 5；票 06e 拆出來的那一格）。 */
const AT_TMDB = setupStatus({ ...AT_BERTH_TWO, current_step: 7 })

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

describe('泊位 4：索引站', () => {
  it('預設站預設全勾，按鈕說得出會加幾個', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: indexerSetup() } })

    renderWithProviders(<SetupPage />)

    const picks = (await screen.findByText('要加入哪些站')).closest('fieldset')!
    const boxes = within(picks).getAllByRole('checkbox')
    expect(boxes).toHaveLength(9)
    expect(boxes.every((box) => (box as HTMLInputElement).checked)).toBe(true)
    expect(screen.getByRole('button', { name: '加入這 9 個站' })).toBeInTheDocument()
    // AniDex 不在預設清單裡（票 06e：anidex.info 從 09-08 起一直回 502）。
    expect(within(picks).queryByLabelText('Anidex')).not.toBeInTheDocument()
  })

  it('每一站說出是什麼語言（照 UI 語言的名字）與一句原文說明', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: indexerSetup() } })

    renderWithProviders(<SetupPage />)

    const dmhy = await screen.findByLabelText('dmhy')
    expect(dmhy).toHaveAccessibleDescription(
      '中文（台灣） · dmhy is a TAIWANESE Public magnet tracker for ANIME',
    )
    expect(screen.getByLabelText('Mikan')).toHaveAccessibleDescription('中文（中國）')
    expect(screen.getByLabelText('Anime Tosho')).toHaveAccessibleDescription(
      '英文（美國） · 半私有站，可能需要帳號',
    )
  })

  it('取消勾選的站不會被送出去', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [ADD_INDEXERS]: { body: indexerSetup({ steps: [step('nyaasi', 'ok')] }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const picks = (await screen.findByText('要加入哪些站')).closest('fieldset')!
    await user.click(within(picks).getByLabelText('The Pirate Bay'))
    await user.click(screen.getByRole('button', { name: '加入這 8 個站' }))

    const call = fetchStub.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(call[1]?.body)).indexers).not.toContain('thepiratebay')
    expect(JSON.parse(String(call[1]?.body)).indexers).toContain('nyaasi')
  })

  it('逐站顯示成敗：連不上的變紅並展開手動步驟，其餘照樣繫上', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
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

  it('探測到、還沒加站時，板上那一格說「Prowlarr · 尚未加入索引站」', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: indexerSetup() } })

    renderWithProviders(<SetupPage />)

    const berth = within((await screen.findByText('BTH 4')).closest('li')!)
    expect(berth.getByText('索引站')).toBeInTheDocument()
    expect(await berth.findByText('Prowlarr · 尚未加入索引站')).toBeInTheDocument()
  })

  it('判定沒有站數時（例如缺 API key）那一格不說「尚未加入」，留破折號', async () => {
    const missingKey = detection({
      kind: 'prowlarr',
      origin: 'existing',
      reason: 'api_key_missing',
      detail: '',
      base_url: 'http://nas:9696',
    })
    stubApi({
      [STATUS]: {
        body: setupStatus({ ...AT_BERTH_TWO, services: [...ALL_BUNDLED.slice(0, 2), missingKey] }),
      },
    })

    renderWithProviders(<SetupPage />)

    const berth = within((await screen.findByText('BTH 4')).closest('li')!)
    expect(berth.queryByText(/尚未加入索引站/)).not.toBeInTheDocument()
    expect(berth.getByText('—')).toBeInTheDocument()
  })

  it('加完站之後那一格說出加了幾站', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: withSites() } })

    renderWithProviders(<SetupPage />)

    const berth = within((await screen.findByText('BTH 4')).closest('li')!)
    expect(await berth.findByText('Prowlarr · 3 個索引站')).toBeInTheDocument()
  })

  it('加入之後可以試搜：逐站列出筆數與前三筆標題，一站失敗不影響其他站', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: withSites() },
      [`${SEARCH}?query=Frieren`]: {
        body: {
          query: 'Frieren',
          error: '',
          sites: [
            siteSearch(1, 'dmhy', 12, ['[LoliHouse] Frieren - 28', 'b', 'c']),
            siteSearch(2, 'Mikan', 0, [], 'GET /api/v1/search: 502 Bad Gateway'),
            siteSearch(3, 'YTS', 0, []),
          ],
        },
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const trial = within((await screen.findByRole('heading', { name: '試搜' })).closest('section')!)
    // 還沒按之前，加進來的每一站都在清單上，說它還沒試搜。
    expect(trial.getAllByText('還沒試搜')).toHaveLength(3)

    await user.type(trial.getByLabelText('關鍵字'), 'Frieren')
    await user.click(trial.getByRole('button', { name: '試搜' }))

    const rows = within(await screen.findByTestId('trial'))
    expect(await rows.findByText('12 筆')).toBeInTheDocument()
    expect(rows.getByText('[LoliHouse] Frieren - 28')).toBeInTheDocument()
    expect(rows.getByText('GET /api/v1/search: 502 Bad Gateway')).toBeInTheDocument()
    expect(rows.getByText('0 筆')).toBeInTheDocument()
    const call = fetchStub.mock.calls.find(([url]) => String(url).includes('/indexers/search'))!
    expect(String(call[0])).toContain('query=Frieren')
  })

  it('每一站可以移除，就地確認之後才送出', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: withSites() },
      [REMOVE_YTS]: {
        body: indexerSetup({
          options: DEFAULT_OPTIONS.map((row) =>
            row.definition_name === 'dmhy'
              ? added(row, 1)
              : row.definition_name === 'mikan'
                ? added(row, 2)
                : row,
          ),
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const trial = await screen.findByTestId('trial')
    const yts = within(within(trial).getByText('YTS').closest('li')!)
    await user.click(yts.getByRole('button', { name: '移除' }))

    // 第一下只展開確認，什麼都還沒送。
    expect(fetchStub.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    expect(yts.getByText(/從 Prowlarr 移除 YTS/)).toBeInTheDocument()
    await user.click(yts.getByRole('button', { name: '確定移除' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('trial')).queryByText('YTS')).not.toBeInTheDocument()
    })
    const call = fetchStub.mock.calls.find(([, init]) => init?.method === 'DELETE')!
    expect(String(call[0])).toMatch(/\/setup\/indexers\/3$/)
    // 那一列連同觸發鍵一起消失：焦點落在接替那個位置的那一列，另有一行說結果（The Focus Takes The Next Row Rule）。
    await waitFor(() => expect(document.activeElement).toHaveAccessibleName('Mikan'))
    expect(screen.getByText('已從 Prowlarr 移除 YTS。')).toHaveClass('sr-only')
  })

  it('既有路徑可以填任意 Torznab 端點，接上之後照樣試搜，但沒有移除', async () => {
    const connected = indexerSetup({
      origin: 'existing',
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      options: [],
      steps: [step('torznab', 'ok', 'Jackett · TV')],
    })
    const fetchStub = stubApi({
      [STATUS]: { body: AT_EXISTING_INDEXER },
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', base_url: '', options: [] }) },
      [CONNECT_INDEXER]: { body: connected },
      [`${SEARCH}?query=`]: {
        body: { query: '', error: '', sites: [siteSearch(null, 'jackett:9117', 4, ['x'])] },
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
    // 板上那一格說出實際的那一種，不寫死 Prowlarr。
    const berth = within(screen.getByText('BTH 4').closest('li')!)
    expect(berth.getByText('Torznab · jackett:9117')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '試搜' }))
    const rows = within(await screen.findByTestId('trial'))
    expect(await rows.findByText('4 筆')).toBeInTheDocument()
    expect(rows.queryByRole('button', { name: '移除' })).not.toBeInTheDocument()
  })

  it('索引站可以之後再說，而且跳過之後畫面上看得出來', async () => {
    // 這一條原本只驗「請求送出去了」，於是「送出去了但畫面沒變」一直沒被抓到：
    // TMDB 那一節有徽章，索引站那一節沒有，按了像壞掉（票 11 的 critique）。
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [SKIP_INDEXERS]: { body: indexerSetup({ skipped: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    expect(screen.queryByTestId('indexers-deferred')).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: '之後再說' }))

    await waitFor(() => {
      expect(fetchStub.mock.calls.some(([url]) => String(url).endsWith('/indexers/skip'))).toBe(
        true,
      )
    })
    expect(await screen.findByTestId('indexers-deferred')).toBeInTheDocument()
  })

  /**
   * 票 03 第 12 條。API key 與密碼同級：都是貼上去就不該留在畫面上的憑證。
   * 遮起來之後仍然看得見——`PasswordField` 自己帶一顆「顯示」。
   */
  it('既有索引站的 API key 是遮著的，且看得見', async () => {
    stubApi({
      [STATUS]: { body: AT_EXISTING_INDEXER },
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', api_key_present: false }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    const indexerKey = await screen.findByLabelText('API key')
    expect(indexerKey).toHaveAttribute('type', 'password')
    await user.click(
      within(indexerKey.closest('div.relative')!).getByRole('button', { name: '顯示' }),
    )
    expect(screen.getByLabelText('API key')).toHaveAttribute('type', 'text')
  })
})

describe('泊位 5：TMDB', () => {
  it('TMDB 是自己的一格、自己的一頁，沒有「之後再說」', async () => {
    stubApi({ [STATUS]: { body: AT_TMDB }, [TMDB]: { body: tmdbSetup() } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('heading', { level: 2, name: 'TMDB' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '之後再說' })).not.toBeInTheDocument()
    expect(screen.queryByText('要加入哪些站')).not.toBeInTheDocument()
    const berth = within(screen.getByText('BTH 5').closest('li')!)
    expect(berth.getByText('TMDB')).toBeInTheDocument()
    expect(berth.getByRole('button')).toHaveAttribute('aria-current', 'step')
  })

  it('沒填 key 就按下去會被欄位擋住，畫面說得出去哪裡拿一把', async () => {
    // 第 7 步是閘門（票 02b）：第一次來的人手上還沒有 key，所以畫面要先說去哪裡申請。
    // 按鈕**不停用**——票 11 的 critique 抓過「按不動的控制項讀起來像壞掉」。
    const fetchStub = stubApi({ [STATUS]: { body: AT_TMDB }, [TMDB]: { body: tmdbSetup() } })
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
      [STATUS]: { body: AT_TMDB },
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
      [STATUS]: { body: AT_TMDB },
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

  it('TMDB 的 key 是遮著的，且看得見', async () => {
    stubApi({ [STATUS]: { body: AT_TMDB }, [TMDB]: { body: tmdbSetup() } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    const tmdbKey = await screen.findByLabelText('你的 TMDB API key')
    expect(tmdbKey).toHaveAttribute('type', 'password')
    await user.click(within(tmdbKey.closest('div.relative')!).getByRole('button', { name: '顯示' }))
    expect(screen.getByLabelText('你的 TMDB API key')).toHaveAttribute('type', 'text')
  })

  /**
   * 票 03 第 4 條：閘門過了，板上那一格要跟著動。票 06e 之後 TMDB 是自己的一格，
   * 它的詳情列只說憑證；索引站那一格不再被換掉。
   */
  it('通過 TMDB 閘門之後，TMDB 那一格的詳情列跟著換', async () => {
    stubApi({
      [STATUS]: { body: AT_TMDB },
      [INDEXERS]: { body: withSites() },
      [TMDB]: { body: tmdbSetup({ api_key_present: true }) },
      [TEST_TMDB]: { body: tmdbSetup({ api_key_present: true, verified: true, steps: [] }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const berth = within((await screen.findByText('BTH 5')).closest('li')!)
    expect(await berth.findByText('待驗證')).toBeInTheDocument()

    await user.type(await screen.findByLabelText('你的 TMDB API key'), '0'.repeat(32))
    await user.click(screen.getByRole('button', { name: '測試 TMDB' }))

    expect(await berth.findByText('已驗證')).toBeInTheDocument()
    expect(berth.queryByText('待驗證')).not.toBeInTheDocument()
    const indexers = within(screen.getByText('BTH 4').closest('li')!)
    expect(indexers.getByText('Prowlarr · 3 個索引站')).toBeInTheDocument()
  })
})

/** dmhy、Mikan、YTS 三站已經加進套件內的 Prowlarr（id 1–3）。 */
function withSites() {
  const ids: Record<string, number> = { dmhy: 1, mikan: 2, yts: 3 }
  return indexerSetup({
    options: DEFAULT_OPTIONS.map((row) =>
      row.definition_name in ids ? added(row, ids[row.definition_name]) : row,
    ),
    steps: [step('dmhy', 'ok'), step('mikan', 'ok'), step('yts', 'ok')],
  })
}

function siteSearch(
  indexer_id: number | null,
  name: string,
  count: number,
  titles: string[],
  error = '',
): SiteSearch {
  return { indexer_id, definition_name: name.toLowerCase(), name, count, titles, error }
}

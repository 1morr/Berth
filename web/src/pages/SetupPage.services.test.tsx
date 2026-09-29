import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import type { SiteSearch } from '../api/setup'
import {
  ALL_BUNDLED,
  DEFAULT_OPTIONS,
  added,
  chosen,
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
const CHOOSE_QBITTORRENT = 'POST /api/setup/services/qbittorrent'
const RETEST_QBITTORRENT = 'POST /api/setup/services/qbittorrent/test'
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

/** 介面登入預設沿用 Jellyfin 帳密（M4 票 15）：只有一格擁有者的密碼。 */
const OWNER_PASSWORD = 'skipper 的 Jellyfin 密碼'

/** 取消勾選「沿用」之後的三格（M4 票 07）：帳號預填擁有者的名字，密碼打兩次。 */
async function typeOwnLogin(
  user: UserEvent,
  fields: ReturnType<typeof within>,
  confirm = 'harbour',
) {
  await user.type(fields.getByLabelText('密碼'), 'harbour')
  await user.type(fields.getByLabelText('再輸入一次密碼'), confirm)
}

function bodyOf(stub: ReturnType<typeof stubApi>, url: string) {
  const call = stub.mock.calls.find(([called]) => called === url)!
  return JSON.parse(String(call[1]?.body)) as Record<string, unknown>
}

function called(stub: ReturnType<typeof stubApi>, url: string) {
  return stub.mock.calls.some(([each]) => each === url)
}

/** 二選一的那兩格。label 裡還有說明句與位址，所以只比開頭。 */
const bundledCard = () => screen.getByRole('radio', { name: /^套件內/ })
const existingCard = () => screen.getByRole('radio', { name: /^既有/ })

const EXISTING_QBITTORRENT = chosen({
  kind: 'qbittorrent',
  origin: 'existing',
  base_url: 'http://nas:8080',
  reason: 'connected',
  detail: 'v5.2.3 · Web API 2.15.1',
})

/** 擁有者成立了，精靈在頁 2，qBittorrent 還沒選。 */
const CHOOSING_QBITTORRENT = setupStatus({
  current_step: 2,
  owner: 'skipper',
  services: [ALL_BUNDLED[0]],
})

/** 同一頁，選了套件內而且連上了。 */
const AT_QBITTORRENT = setupStatus({ ...CHOOSING_QBITTORRENT, services: ALL_BUNDLED.slice(0, 2) })

/** 同一頁，選了使用者自己的那一台。 */
const AT_EXISTING_QBITTORRENT = setupStatus({
  ...CHOOSING_QBITTORRENT,
  services: [ALL_BUNDLED[0], EXISTING_QBITTORRENT],
})

/** 自己的 qBittorrent 的差異：一個鍵都不寫、沒有 WebUI 登入那一格（M4 票 05、07）。 */
const EXISTING_DIFF = qbittorrentSetup({
  origin: 'existing',
  base_url: 'http://nas:8080',
  web_ui_login: false,
  web_ui_username: '',
  writes_preferences: false,
})

/** 三個服務都接好、媒體庫路徑也過了，精靈在索引站（頁 4）。 */
const AT_INDEXER = setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED })

/** 同一頁，Prowlarr 還沒選。 */
const CHOOSING_INDEXER = setupStatus({ ...AT_INDEXER, services: ALL_BUNDLED.slice(0, 2) })

/** 索引站有結論了，精靈在 TMDB（頁 5）。 */
const AT_TMDB = setupStatus({ ...AT_INDEXER, current_step: 5 })

describe('頁 2：qBittorrent', () => {
  /** M4 票 15 驗收：選之前一個請求都不發——差異要連那一台才讀得到。 */
  it('選之前不讀差異、不測 qBittorrent', async () => {
    const stub = stubApi({
      [STATUS]: { body: CHOOSING_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
    })

    renderWithProviders(<SetupPage />)

    expect(
      await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' }),
    ).toBeVisible()
    expect(bundledCard()).not.toBeChecked()
    expect(existingCard()).not.toBeChecked()
    expect(screen.queryByText('將會寫入的鍵')).not.toBeInTheDocument()
    expect(called(stub, '/api/setup/qbittorrent/diff')).toBe(false)
    expect(stub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  /** 票 06h：`.env` 換了 `QBITTORRENT_WEBUI_PORT`，畫面原本照樣寫 `qbittorrent:8080`。 */
  it('套件內那一格的位址照後端說的寫，不寫死 port', async () => {
    const targets = { ...setupStatus().bundled_targets, qbittorrent: 'http://qbittorrent:18080' }
    stubApi({
      [STATUS]: { body: setupStatus({ ...CHOOSING_QBITTORRENT, bundled_targets: targets }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('http://qbittorrent:18080')).toBeInTheDocument()
    expect(screen.queryByText(/qbittorrent:8080/)).not.toBeInTheDocument()
  })

  it('點「套件內」就送出選擇，連上了才讀差異', async () => {
    const stub = stubApi({
      [STATUS]: { body: CHOOSING_QBITTORRENT },
      [CHOOSE_QBITTORRENT]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
    await user.click(bundledCard())

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/services/qbittorrent')).toEqual({ origin: 'bundled' }),
    )
    expect(await screen.findByText('將會寫入的鍵')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: '套用建議的 qBittorrent 設定' }),
    ).toBeVisible()
    expect(called(stub, '/api/setup/qbittorrent/diff')).toBe(true)
  })

  it('點「既有」只展開表單；按「測試連線」才送位址與 WebUI 帳密', async () => {
    const stub = stubApi({
      [STATUS]: { body: CHOOSING_QBITTORRENT },
      [CHOOSE_QBITTORRENT]: { body: AT_EXISTING_QBITTORRENT },
      [DIFF]: { body: EXISTING_DIFF },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
    await user.click(existingCard())

    const address = screen.getByRole('textbox', { name: '位址' })
    // 位址的範例是 qBittorrent 自己的 port，不是 Jellyfin 的 8096（票 06h）。
    expect(address).toHaveAttribute('placeholder', 'http://192.168.1.10:8080')
    expect(screen.getByText('COMPOSE_PROFILES=jellyfin,prowlarr')).toBeInTheDocument()
    expect(stub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    expect(called(stub, '/api/setup/qbittorrent/diff')).toBe(false)

    await user.type(address, 'http://nas:8080')
    await user.type(screen.getByLabelText('帳號'), 'admin')
    await user.type(screen.getByLabelText('密碼'), 'adminadmin')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/services/qbittorrent')).toEqual({
        origin: 'existing',
        base_url: 'http://nas:8080',
        api_key: '',
        username: 'admin',
        password: 'adminadmin',
      }),
    )
    expect(
      await screen.findByRole('heading', { level: 2, name: '確認你的 qBittorrent' }),
    ).toBeVisible()
  })

  it('套件內那一台逾時：給診斷指令，「重新測試」重算上限', async () => {
    const timedOut = chosen({
      ...ALL_BUNDLED[1],
      state: 'timeout',
      reason: 'unreachable',
      detail: '',
      waited_seconds: 121,
    })
    const stub = stubApi({
      [STATUS]: {
        body: setupStatus({ ...CHOOSING_QBITTORRENT, services: [ALL_BUNDLED[0], timedOut] }),
      },
      [RETEST_QBITTORRENT]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('docker compose ps qbittorrent')).toBeInTheDocument()
    expect(screen.getByText('逾時')).toBeInTheDocument()
    // 連不上就沒有差異可讀。
    expect(called(stub, '/api/setup/qbittorrent/diff')).toBe(false)

    await user.click(screen.getByRole('button', { name: '重新測試' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/services/qbittorrent/test')).toEqual({ restart: true }),
    )
    expect(await screen.findByText('將會寫入的鍵')).toBeInTheDocument()
  })

  it('剖面在按之前就逐鍵列出現值與建議值', async () => {
    stubApi({ [STATUS]: { body: AT_QBITTORRENT }, [DIFF]: { body: qbittorrentSetup() } })

    renderWithProviders(<SetupPage />)
    const diff = (await screen.findByText('將會寫入的鍵')).closest('section')!

    expect(within(diff).getByText('temp_path_enabled')).toBeInTheDocument()
    expect(within(diff).getByText('/data/torrent/incomplete')).toBeInTheDocument()
    // 現值也在同一列，使用者看得出來按下去會改掉什麼。
    expect(within(diff).getByText('/downloads/incomplete')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '套用這 5 個鍵' })).toBeInTheDocument()
  })

  it('WebUI 登入預設沿用 Jellyfin 帳密：只有一格密碼，套用之後逐鍵留下結果', async () => {
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
      web_ui_username: 'skipper',
    })
    const stub = stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
      [APPLY]: { body: applied },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const legend = await screen.findByText('qBittorrent WebUI 登入')
    const fields = within(legend.closest('fieldset')!)
    expect(fields.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' })).toBeChecked()
    // 說得出這是 qBittorrent 自己的登入、Berth 用不到它。
    expect(fields.getByText(/Berth 自己用不到它/)).toBeInTheDocument()
    expect(fields.queryByLabelText('帳號')).not.toBeInTheDocument()
    expect(fields.queryByLabelText('再輸入一次密碼')).not.toBeInTheDocument()

    await user.type(fields.getByLabelText(OWNER_PASSWORD), 'harbour')
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))

    const sequence = await screen.findByTestId('sequence')
    await waitFor(() => {
      expect(within(sequence).getAllByText('已完成')).toHaveLength(5)
    })
    expect(within(sequence).getByText('已經是這樣')).toBeInTheDocument()
    expect(within(sequence).getByText('WebUI 登入')).toBeInTheDocument()
    // 沿用時帳號留空：後端填成擁有者。
    expect(bodyOf(stub, '/api/setup/qbittorrent/apply')).toEqual({
      login: { username: '', password: 'harbour', reuse_owner: true },
    })
    // 設好之後欄位收起來，只說帳號是誰。
    expect(await screen.findByText('qBittorrent WebUI 的帳號：')).toBeInTheDocument()
    expect(screen.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
  })

  it('沿用時沒填密碼就不送', async () => {
    const stub = stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
      [APPLY]: { body: qbittorrentSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '套用這 5 個鍵' }))

    expect(await screen.findByText('這一格要填。')).toBeInTheDocument()
    expect(called(stub, '/api/setup/qbittorrent/apply')).toBe(false)
  })

  it('取消沿用是自設的三格：帳號預填擁有者，沒填或兩次不同就不送，送的是 reuse_owner:false', async () => {
    const stub = stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
      [APPLY]: { body: qbittorrentSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const legend = await screen.findByText('qBittorrent WebUI 登入')
    const fields = within(legend.closest('fieldset')!)
    await user.click(fields.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' }))

    expect(fields.getByLabelText('帳號')).toHaveValue('skipper')
    expect(fields.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))
    expect(await fields.findByText('這一格要填。')).toBeInTheDocument()
    await typeOwnLogin(user, fields, 'harbor')
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))
    expect(await fields.findByText('兩次輸入的密碼不一樣。')).toBeInTheDocument()
    expect(called(stub, '/api/setup/qbittorrent/apply')).toBe(false)

    await user.clear(fields.getByLabelText('再輸入一次密碼'))
    await user.type(fields.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/qbittorrent/apply')).toEqual({
        login: { username: 'skipper', password: 'harbour', reuse_owner: false },
      }),
    )
  })

  it('沿用的密碼不是擁有者的 Jellyfin 密碼時，畫面說出來而且什麼都沒寫', async () => {
    stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup() },
      [APPLY]: { status: 422, body: { detail: { reason: 'owner_password', detail: '' } } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText(OWNER_PASSWORD), 'wrong')
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))

    expect(
      await screen.findByText('這不是 skipper 的 Jellyfin 密碼，所以什麼都沒寫；改好再按一次。'),
    ).toBeVisible()
    // 欄位留著，改一個字再按。
    expect(screen.getByLabelText(OWNER_PASSWORD)).toHaveValue('wrong')
  })

  it('那一台自己就設過登入時欄位收起來、說出帳號，重按不帶登入；按「更換登入」才打開', async () => {
    const set = qbittorrentSetup({ web_ui_username: 'admin' })
    const stub = stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
      [DIFF]: { body: set },
      [APPLY]: { body: set },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    expect(await screen.findByText('qBittorrent WebUI 的帳號：')).toHaveTextContent(
      'qBittorrent WebUI 的帳號： admin',
    )
    expect(screen.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('密碼')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '套用這 5 個鍵' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/qbittorrent/apply')).toEqual({ login: null }),
    )
    await user.click(screen.getByRole('button', { name: '更換登入' }))
    expect(screen.getByLabelText(OWNER_PASSWORD)).toBeInTheDocument()
    // 取消沿用時帳號預填那一台現在的帳號，不是擁有者。
    await user.click(screen.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' }))
    expect(screen.getByLabelText('帳號')).toHaveValue('admin')
  })

  it('已經套用過時換成既有要先看過後果，不當場送出；點回原本那一格就是不換', async () => {
    const applied = qbittorrentSetup({
      steps: [step('temp_path_enabled', 'ok', 'true')],
      web_ui_username: 'skipper',
    })
    const stub = stubApi({ [STATUS]: { body: AT_QBITTORRENT }, [DIFF]: { body: applied } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByText('將會寫入的鍵')
    await user.click(existingCard())

    expect(screen.getByText(/Berth 已經寫進原本那一台的偏好與登入留在那裡/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '位址' })).toBeInTheDocument()
    expect(stub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)

    await user.click(bundledCard())
    expect(
      screen.queryByText(/Berth 已經寫進原本那一台的偏好與登入留在那裡/),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '位址' })).not.toBeInTheDocument()
  })

  it('已經確認過既有的那一台時換成套件內要先確認，按了才送出', async () => {
    const confirmed = qbittorrentSetup({
      ...EXISTING_DIFF,
      steps: [step('temp_path_enabled', 'skipped', 'true')],
    })
    const stub = stubApi({
      [STATUS]: { body: AT_EXISTING_QBITTORRENT },
      [DIFF]: { body: confirmed },
      [CHOOSE_QBITTORRENT]: { body: AT_QBITTORRENT },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '確認你的 qBittorrent' })
    await user.click(bundledCard())

    expect(screen.getByText(/Berth 已經寫進原本那一台的偏好與登入留在那裡/)).toBeInTheDocument()
    expect(called(stub, '/api/setup/services/qbittorrent')).toBe(false)
    await user.click(screen.getByRole('button', { name: '改用套件內的那一台' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/setup/services/qbittorrent')).toEqual({ origin: 'bundled' }),
    )
  })

  it('版本太舊時給的是升級指令，不是一顆按不動的按鈕', async () => {
    stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
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

  it('既有服務只列現值與建議值、不寫任何鍵；temp path 未啟用只是警告（M4 票 05）', async () => {
    stubApi({
      [STATUS]: { body: AT_EXISTING_QBITTORRENT },
      [DIFF]: { body: qbittorrentSetup({ ...EXISTING_DIFF, temp_path_warning: true }) },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/沒有啟用未完成目錄/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '確認你的 qBittorrent', level: 2 })).toBeVisible()
    // 剖面照樣逐鍵列出，但說的是「不會寫入」，不是「將會寫入」。
    expect(screen.getByText('你的偏好（Berth 不會寫入）')).toBeInTheDocument()
    expect(screen.queryByText('將會寫入的鍵')).not.toBeInTheDocument()
    expect(screen.getByText('/downloads')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /套用/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '確認，不改任何設定' })).toBeEnabled()
    // 既有的那一台沒有 WebUI 登入那一格（M4 票 07）。
    expect(screen.queryByText('qBittorrent WebUI 登入')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(OWNER_PASSWORD)).not.toBeInTheDocument()
  })

  it('差異讀回來說連不上時說得出下一步', async () => {
    stubApi({
      [STATUS]: { body: AT_QBITTORRENT },
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

describe('頁 4：Prowlarr 與索引站', () => {
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
    await user.type(screen.getByLabelText(OWNER_PASSWORD), 'harbour')
    await user.click(screen.getByRole('button', { name: '加入這 8 個站' }))

    await waitFor(() =>
      expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/indexers/apply')).toBe(true),
    )
    const body = bodyOf(fetchStub, '/api/setup/indexers/apply')
    expect(body.indexers).not.toContain('thepiratebay')
    expect(body.indexers).toContain('nyaasi')
    // Prowlarr 的介面登入跟著「加入」一起送（M4 票 07），預設沿用 Jellyfin 帳密（M4 票 15）。
    expect(body.login).toEqual({ username: '', password: 'harbour', reuse_owner: true })
  })

  it('Prowlarr 介面登入必填：沒填密碼就不加站（M4 票 07）', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const fields = within((await screen.findByText('Prowlarr 介面登入')).closest('fieldset')!)
    expect(fields.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' })).toBeChecked()
    expect(fields.getByLabelText(OWNER_PASSWORD)).toHaveValue('')
    await user.click(screen.getByRole('button', { name: '加入這 9 個站' }))

    expect(await fields.findByText('這一格要填。')).toBeInTheDocument()
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/indexers/apply')).toBe(false)
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

  it('連上了、還沒加站時，板上那一格說「套件內 · Prowlarr · 尚未加入索引站」', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: indexerSetup() } })

    renderWithProviders(<SetupPage />)

    const berth = within((await screen.findByText('BTH 4')).closest('li')!)
    expect(berth.getByText('索引站')).toBeInTheDocument()
    expect(await berth.findByText('套件內 · Prowlarr · 尚未加入索引站')).toBeInTheDocument()
  })

  it('測試沒有站數時（例如缺 API key）那一格不說「尚未加入」，留破折號', async () => {
    const missingKey = chosen({
      kind: 'prowlarr',
      state: 'failed',
      reason: 'api_key_missing',
      detail: '',
      base_url: 'http://prowlarr:9696',
    })
    stubApi({
      [STATUS]: {
        body: setupStatus({
          ...AT_QBITTORRENT,
          services: [...ALL_BUNDLED.slice(0, 2), missingKey],
        }),
      },
      [DIFF]: { body: qbittorrentSetup() },
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
    expect(await berth.findByText('套件內 · Prowlarr · 3 個索引站')).toBeInTheDocument()
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
    const fetchStub = stubRemoval()
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
    // 那一列連同觸發鍵一起消失，另有一行說結果。
    expect(screen.getByText('已從 Prowlarr 移除 YTS。')).toHaveClass('sr-only')
  })

  /**
   * The Focus Takes The Next Row Rule：焦點落在接替那個位置的那一列。
   *
   * 票 15 一度退化過：頁 4 在清單讀回來之前就掛上 `StepFrame`，它的 MutationObserver 比試搜清單的
   * `useFocusAfterRemoval` 先建立、先跑，焦點被搶到 h2。現在頁 4 讀回來才掛（`SetupPage`）。
   */
  it('移除之後焦點落在接替那個位置的那一列', async () => {
    stubRemoval()
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const trial = await screen.findByTestId('trial')
    const yts = within(within(trial).getByText('YTS').closest('li')!)
    await user.click(yts.getByRole('button', { name: '移除' }))
    await user.click(yts.getByRole('button', { name: '確定移除' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('trial')).queryByText('YTS')).not.toBeInTheDocument()
    })
    await waitFor(() => expect(document.activeElement).toHaveAccessibleName('Mikan'), {
      timeout: 1000,
    })
  })

  it('選「既有」可以填任意 Torznab 端點，接上之後照樣試搜，但沒有移除', async () => {
    const existingProwlarr = chosen({
      kind: 'prowlarr',
      origin: 'existing',
      base_url: 'http://jackett:9117/api',
      reason: 'connected',
      detail: '',
    })
    let connectedYet = false
    const connected = indexerSetup({
      origin: 'existing',
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      options: [],
      steps: [step('torznab', 'ok', 'Jackett · TV')],
    })
    const fetchStub = stubApi({
      // 接上就是選了既有：之後重讀的精靈狀態裡有這一台。
      [STATUS]: () => ({
        body: connectedYet
          ? setupStatus({ ...AT_INDEXER, services: [...ALL_BUNDLED.slice(0, 2), existingProwlarr] })
          : CHOOSING_INDEXER,
      }),
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', base_url: '', options: [] }) },
      [CONNECT_INDEXER]: () => {
        connectedYet = true
        return { body: connected }
      },
      [`${SEARCH}?query=`]: {
        body: { query: '', error: '', sites: [siteSearch(null, 'jackett:9117', 4, ['x'])] },
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '索引站' })
    await user.click(existingCard())
    // 選「既有」只展開表單；Prowlarr 頁的表單自己送 connect，不經 `services/prowlarr`。
    expect(fetchStub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('radio', { name: 'Torznab 端點' }))
    await user.type(screen.getByLabelText('位址'), 'http://jackett:9117/api')
    await user.type(screen.getByLabelText('API key'), 'the-key')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/connect')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/indexers/connect')).toEqual({
      kind: 'torznab',
      base_url: 'http://jackett:9117/api',
      api_key: 'the-key',
    })
    expect(await screen.findByText('Jackett · TV')).toBeInTheDocument()
    // 板上那一格說出實際的那一種，不寫死 Prowlarr。
    const berth = within(screen.getByText('BTH 4').closest('li')!)
    expect(berth.getByText('既有 · Torznab · jackett:9117')).toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: '試搜' }))
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
    // 讀到清單之前頁尾有一顆同名的「之後再說」，讀到之後換成「加入」旁邊那一顆：等清單畫好再按。
    await screen.findByText('要加入哪些站')
    expect(screen.queryByTestId('indexers-deferred')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '之後再說' }))

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
      [STATUS]: { body: CHOOSING_INDEXER },
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', api_key_present: false }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '索引站' })
    await user.click(existingCard())

    const indexerKey = screen.getByLabelText('API key')
    expect(indexerKey).toHaveAttribute('type', 'password')
    await user.click(
      within(indexerKey.closest('div.relative')!).getByRole('button', { name: '顯示' }),
    )
    expect(screen.getByLabelText('API key')).toHaveAttribute('type', 'text')
  })
})

describe('頁 5：TMDB', () => {
  it('TMDB 是自己的一格、自己的一頁，沒有「之後再說」', async () => {
    stubApi({ [STATUS]: { body: AT_TMDB }, [TMDB]: { body: tmdbSetup() } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByRole('heading', { level: 2, name: 'TMDB' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '之後再說' })).not.toBeInTheDocument()
    expect(screen.queryByText('要加入哪些站')).not.toBeInTheDocument()
    const berth = within(screen.getByText('BTH 5').closest('li')!)
    expect(berth.getByText('TMDB')).toBeInTheDocument()
    expect(berth.getByRole('button')).toHaveAttribute('aria-current', 'step')
    // 精靈裡的「去哪裡拿」多一句進度會留著（設定頁沒有這一句，票 06h），兩句之間中文不加空格。
    expect(
      screen.getByText(/不必等審核。現在就去申請也沒關係——精靈的進度已經存下來了/),
    ).toBeVisible()
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
    expect(indexers.getByText('套件內 · Prowlarr · 3 個索引站')).toBeInTheDocument()
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

/** 頁 4 上 dmhy、Mikan、YTS 三站都在，移除 YTS 之後剩兩站。 */
function stubRemoval() {
  return stubApi({
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
}

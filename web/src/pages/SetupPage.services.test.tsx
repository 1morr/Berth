import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import type { SiteFailure, SiteSearch } from '../api/setup'
import {
  ALL_BUNDLED,
  OTHER_PUBLIC,
  RECOMMENDED,
  check,
  chosen,
  indexerSetup,
  qbittorrentSetup,
  setupStatus,
  site,
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
const TEST_SITES = 'POST /api/setup/indexers/test'
const CONNECT_INDEXER = 'POST /api/setup/indexers/connect'
const SKIP_INDEXERS = 'POST /api/setup/indexers/skip'
const SET_LOGIN = 'PUT /api/setup/indexers/login'
const RETEST_PROWLARR = 'POST /api/setup/services/prowlarr/test'
const SEARCH = 'GET /api/setup/indexers/search'
const REMOVE_YTS = 'DELETE /api/setup/indexers/3'
const TMDB = 'GET /api/setup/tmdb'
const TEST_TMDB = 'POST /api/setup/tmdb/test'

/** Prowlarr 對 1337x 回的原文（brief §20.7 的實測）。 */
const CLOUDFLARE = 'Unable to access 1337x.to, blocked by CloudFlare Protection.'

/** 演練伺服器那四站沒通過的樣子（`scripts/fake_setup_server.py` 的 `BLOCKED_SITES`）。 */
const FOUR_FAILURES: Record<string, [SiteFailure, string]> = {
  nyaasi: ['no_results', 'Query successful, but no results were returned from your indexer.'],
  '1337x': ['cloudflare', CLOUDFLARE],
  eztv: ['cloudflare', 'Unable to access eztvx.to, blocked by CloudFlare Protection.'],
  'animetosho-xyz': ['unreachable', 'Unable to connect to indexer, check the log above.'],
}

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

/**
 * 自己的 qBittorrent：一個鍵都不寫、沒有 WebUI 登入那一格（M4 票 05、07），也沒有偏好表——
 * 它的全域偏好沒有一個影響 Berth（M4 票 22）。
 */
const EXISTING_DIFF = qbittorrentSetup({
  origin: 'existing',
  base_url: 'http://nas:8080',
  diffs: [],
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

    // 鍵用人話的名字（M4 票 21）：原始鍵名在那一條纜繩的技術細節裡。
    expect(within(diff).getByText('完成目錄')).toBeInTheDocument()
    expect(within(diff).getByText('/data/torrent/complete')).toBeInTheDocument()
    // 現值也在同一列，使用者看得出來按下去會改掉什麼。
    expect(within(diff).getByText('/downloads')).toBeInTheDocument()
    // 未完成目錄不寫全域（M4 票 22）：Berth 的分類各自帶。
    expect(within(diff).queryByText('temp_path_enabled')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '套用這 4 項' })).toBeInTheDocument()
  })

  it('WebUI 登入預設沿用 Jellyfin 帳密：只有一格密碼，套用之後逐鍵留下結果', async () => {
    const applied = qbittorrentSetup({
      diffs: qbittorrentSetup().diffs.map((row) => ({
        ...row,
        current: row.recommended,
        differs: false,
      })),
      steps: [
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
    await user.click(screen.getByRole('button', { name: '套用這 4 項' }))

    const sequence = await screen.findByTestId('sequence')
    await waitFor(() => {
      expect(within(sequence).getAllByText('已完成')).toHaveLength(3)
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
    await user.click(await screen.findByRole('button', { name: '套用這 4 項' }))

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
    await user.click(screen.getByRole('button', { name: '套用這 4 項' }))
    expect(await fields.findByText('這一格要填。')).toBeInTheDocument()
    await typeOwnLogin(user, fields, 'harbor')
    await user.click(screen.getByRole('button', { name: '套用這 4 項' }))
    expect(await fields.findByText('兩次輸入的密碼不一樣。')).toBeInTheDocument()
    expect(called(stub, '/api/setup/qbittorrent/apply')).toBe(false)

    await user.clear(fields.getByLabelText('再輸入一次密碼'))
    await user.type(fields.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '套用這 4 項' }))

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
    await user.click(screen.getByRole('button', { name: '套用這 4 項' }))

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
    // 登入照舊就不算在要寫的那幾項裡（M4 票 21：按鈕的數字與畫面上會寫的對得上）。
    await user.click(screen.getByRole('button', { name: '套用這 3 項' }))

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
      steps: [step('save_path', 'ok', '/data/torrent/complete')],
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

  /**
   * 票 15 critique / audit 的 P2（M4 票 09）：確認走 `ConfirmPanel`——焦點進去、Esc 收起回到原本那一格；
   * 確認之前標題就跟著草稿；從既有換走時 Berth 沒寫過那一台的偏好，警告不這麼說。
   */
  it('已經確認過既有的那一台時換成套件內要先確認：焦點進確認區、Esc 收起，按了才送出', async () => {
    const confirmed = qbittorrentSetup({
      ...EXISTING_DIFF,
      steps: [step('web_ui_password', 'skipped')],
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

    const panel = screen.getByRole('group', { name: /換一台 qBittorrent/ })
    await waitFor(() => expect(panel).toHaveFocus())
    expect(panel).toHaveTextContent(/Berth 沒改過你那一台的偏好/)
    expect(panel).not.toHaveTextContent(/寫進原本那一台的偏好/)
    // 確認之前標題已經說套件內那一台的事。
    expect(screen.queryByRole('heading', { level: 2, name: '確認你的 qBittorrent' })).toBeNull()
    expect(called(stub, '/api/setup/services/qbittorrent')).toBe(false)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group', { name: /換一台 qBittorrent/ })).not.toBeInTheDocument()
    expect(existingCard()).toHaveFocus()
    expect(existingCard()).toBeChecked()
    expect(screen.getByRole('heading', { level: 2, name: '確認你的 qBittorrent' })).toBeVisible()

    await user.click(bundledCard())
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

  /**
   * M4 票 22：接既有 qBittorrent 時不再說「沒有啟用未完成目錄」——那句的理由不成立（完成看的是
   * qBittorrent 回報的狀態），而未完成目錄現在開在 Berth 的分類上。它的全域偏好也不列：沒有一個
   * 影響 Berth，列出套件內的建議值只會讓人以為該去改。
   */
  it('既有服務不寫任何鍵，也不列偏好表、不警告未完成目錄（M4 票 05、22）', async () => {
    stubApi({ [STATUS]: { body: AT_EXISTING_QBITTORRENT }, [DIFF]: { body: EXISTING_DIFF } })

    renderWithProviders(<SetupPage />)

    expect(
      await screen.findByRole('heading', { name: '確認你的 qBittorrent', level: 2 }),
    ).toBeVisible()
    // 標題照選下的來源，不等差異讀回來（M4 票 21）；按鈕等差異回來才有。
    expect(await screen.findByRole('button', { name: '確認，不改任何設定' })).toBeEnabled()
    expect(screen.queryByText(/沒有啟用未完成目錄/)).not.toBeInTheDocument()
    expect(screen.queryByText('將會寫入的鍵')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
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
  it('進這一頁只讀：不測任何一站、不送任何寫入，一站都不預勾', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
    })

    renderWithProviders(<SetupPage />)

    const recommended = within(await screen.findByTestId('recommended'))
    const boxes = recommended.getAllByRole('checkbox')
    expect(boxes).toHaveLength(9)
    expect(boxes.every((box) => !(box as HTMLInputElement).checked)).toBe(true)
    expect(recommended.getAllByText('未測')).toHaveLength(9)
    expect(fetchStub.mock.calls.every(([, init]) => (init?.method ?? 'GET') === 'GET')).toBe(true)
    // 一站都沒勾、登入也還沒填：主鈕說的是設登入，不是「加入 9 個站」。
    expect(screen.getByRole('button', { name: '設定介面登入' })).toBeInTheDocument()
  })

  it('沒測過或測試沒通過的站勾不起來；測過通過的才勾得起來', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: { body: { checks: [check('yts'), check('1337x', 'cloudflare', CLOUDFLARE)] } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const yts = await screen.findByRole('checkbox', { name: 'YTS' })
    const blocked = screen.getByRole('checkbox', { name: '1337x' })
    expect(yts).toBeDisabled()
    expect(yts).toHaveAccessibleDescription(/先測試，通過才勾得起來/)

    await user.click(screen.getByRole('button', { name: '測試 YTS' }))
    await user.click(screen.getByRole('button', { name: '測試 1337x' }))

    await waitFor(() => expect(yts).toBeEnabled())
    expect(blocked).toBeDisabled()
    // 測過而沒通過的不再叫人先測試：理由在那一列上。
    expect(blocked).not.toHaveAccessibleDescription(/先測試/)
    await user.click(yts)
    expect(yts).toBeChecked()
    expect(screen.getByRole('button', { name: '加入 1 個站' })).toBeInTheDocument()
    expect(bodyOf(fetchStub, TEST_SITES.replace('POST ', ''))).toEqual({ indexers: ['yts'] })
  })

  it('「測試全部」測推薦清單裡還沒通過的站', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: { body: { checks: RECOMMENDED.map((row) => check(row.definition_name)) } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試全部' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/test')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/indexers/test').indexers).toEqual(
      RECOMMENDED.map((row) => row.definition_name),
    )
    expect(await screen.findAllByText('通過')).toHaveLength(9)
    // 全過了：沒有還要測的，「測試全部」停用。
    expect(screen.getByRole('button', { name: '測試全部' })).toBeDisabled()
  })

  /**
   * 票 15 critique 的 P1，照演練伺服器的四站失敗（`scripts/fake_setup_server.py` 的 `BLOCKED_SITES`）：
   * 原文不直接攤開、一條摘要一個 live 區、沒有容器主機名的連結、紅色不用在這裡。
   */
  it('四站沒通過：各說一句理由，原文收起來，只有一條摘要、一個 live 區', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: {
        body: {
          checks: RECOMMENDED.map((row) =>
            FOUR_FAILURES[row.definition_name]
              ? check(row.definition_name, ...FOUR_FAILURES[row.definition_name])
              : check(row.definition_name),
          ),
        },
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試全部' }))

    const summary = await screen.findByTestId('check-summary')
    await within(summary).findByText('4 站沒通過')
    expect(summary).toHaveAttribute('aria-live', 'polite')
    expect(summary).toHaveTextContent('Cloudflare 擋住 2 · 查無結果 1 · 連不上 1 · 5 站通過')
    const add = within(screen.getByRole('region', { name: '加站' }))
    expect(add.getAllByText(/被 Cloudflare 擋住/)).toHaveLength(2)
    expect(add.getByText(/連得上，但測試那一次查詢什麼都沒回/)).toBeVisible()
    // 原文在「技術細節」底下，沒有展開就看不到（M4 票 21 統一了這個元件）。
    expect(add.getByText(CLOUDFLARE)).not.toBeVisible()
    expect(add.getAllByText('技術細節')).toHaveLength(4)
    // 這一段只有摘要那一個 live 區，也沒有任何一塊在喊阻擋。
    expect(document.querySelectorAll('[aria-live]:not([role=status])')).toHaveLength(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // 補法連結是使用者瀏覽器到得了的位址，不是 compose 內網的主機名。
    expect(document.body.innerHTML).not.toContain('prowlarr:9696/#')
    expect(add.getByRole('link', { name: '開啟 Prowlarr 的索引站頁' })).toHaveAttribute(
      'href',
      `http://${window.location.hostname}:9696/#/indexers`,
    )
  })

  it('測試的請求沒送到：說在摘要那一個 live 區裡，剛才的站回到未測', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: { status: 502, body: { detail: 'Bad Gateway' } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試 YTS' }))

    const summary = await screen.findByTestId('check-summary')
    expect(await within(summary).findByText(/測試沒有送到/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const yts = within(screen.getByRole('checkbox', { name: 'YTS' }).closest('li')!)
    expect(yts.getByText('未測')).toBeInTheDocument()
  })

  it('主鈕貼著站清單、不必先填介面登入；加入只送勾的那幾站（M4 票 20）', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: { body: { checks: [check('dmhy'), check('mikan')] } },
      [ADD_INDEXERS]: {
        body: indexerSetup({
          sites: [site(RECOMMENDED[1], 1), site(RECOMMENDED[4], 2)],
          steps: [step('dmhy', 'ok'), step('mikan', 'ok'), step('prowlarr_login', 'ok', 'skipper')],
          checks: [check('dmhy'), check('mikan')],
          web_ui_username: 'skipper',
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試 dmhy' }))
    await user.click(screen.getByRole('button', { name: '測試 Mikan' }))
    await user.click(await screen.findByRole('checkbox', { name: 'dmhy' }))
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Mikan' })).toBeEnabled())
    await user.click(screen.getByRole('checkbox', { name: 'Mikan' }))
    // 主鈕在「加站」那一段裡，介面登入是另一區：登入欄空著照樣按得下去。
    const add = within(screen.getByRole('region', { name: '加站' }))
    expect(add.queryByText('Prowlarr 介面登入')).not.toBeInTheDocument()
    await user.click(add.getByRole('button', { name: '加入 2 個站' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/indexers/apply')).toEqual({ indexers: ['dmhy', 'mikan'] })
    expect(called(fetchStub, '/api/setup/indexers/login')).toBe(false)
    // 兩站搬去「已加入」，加站那一段不再有它們；主鈕回到沒有東西可加。
    const added = within(await screen.findByTestId('added'))
    expect(added.getByText('dmhy')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'dmhy' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '加入' })).toBeDisabled()
  })

  it('勾了的站加入時被 Prowlarr 拒了：回到沒通過、理由同一套', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup({ web_ui_username: 'skipper' }) },
      [TEST_SITES]: { body: { checks: [check('eztv')] } },
      [ADD_INDEXERS]: {
        body: indexerSetup({
          web_ui_username: 'skipper',
          steps: [step('eztv', 'failed', '', CLOUDFLARE)],
          checks: [check('eztv', 'cloudflare', CLOUDFLARE)],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '測試 EZTV' }))
    const eztv = screen.getByRole('checkbox', { name: 'EZTV' })
    await waitFor(() => expect(eztv).toBeEnabled())
    await user.click(eztv)
    await user.click(screen.getByRole('button', { name: '加入 1 個站' }))

    await waitFor(() => expect(eztv).toBeDisabled())
    expect(screen.getByText(/被 Cloudflare 擋住/)).toBeInTheDocument()
    expect(screen.getByTestId('check-summary')).toHaveTextContent('1 站沒通過')
  })

  it('Prowlarr 介面登入是自己的一區與按鈕：必填、沒填密碼就不送，填了只送登入（M4 票 07、20）', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [SET_LOGIN]: {
        body: indexerSetup({
          steps: [step('prowlarr_login', 'ok', 'skipper')],
          web_ui_username: 'skipper',
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    const block = within(await screen.findByTestId('prowlarr-login'))
    // 說明寫清楚是必填，以及為什麼（Prowlarr 不讓介面沒有登入）。
    expect(block.getByText('必填')).toBeInTheDocument()
    expect(block.getByText(/關不掉的視窗/)).toBeInTheDocument()
    const fields = within(
      block.getByText('Prowlarr 介面登入', { selector: 'legend' }).closest('fieldset')!,
    )
    expect(fields.getByRole('checkbox', { name: '沿用 Jellyfin 帳密（skipper）' })).toBeChecked()
    await user.click(block.getByRole('button', { name: '設定介面登入' }))

    expect(await fields.findByText('這一格要填。')).toBeInTheDocument()
    expect(called(fetchStub, '/api/setup/indexers/login')).toBe(false)

    await user.type(block.getByLabelText(OWNER_PASSWORD), 'harbour')
    await user.click(block.getByRole('button', { name: '設定介面登入' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/login')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/indexers/login')).toEqual({
      username: '',
      password: 'harbour',
      reuse_owner: true,
    })
    expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(false)
  })

  it('每一站說出是什麼語言（照 UI 語言的名字）與一句原文說明', async () => {
    stubApi({ [STATUS]: { body: AT_INDEXER }, [INDEXERS]: { body: indexerSetup() } })

    renderWithProviders(<SetupPage />)

    const dmhy = within((await screen.findByRole('checkbox', { name: 'dmhy' })).closest('li')!)
    expect(dmhy.getByText('中文（台灣）')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'dmhy' })).toHaveAccessibleDescription(
      'dmhy is a TAIWANESE Public magnet tracker for ANIME · 先測試，通過才勾得起來',
    )
    expect(screen.getByRole('checkbox', { name: 'Anime Tosho' })).toHaveAccessibleDescription(
      '半私有站，可能需要帳號 · 先測試，通過才勾得起來',
    )
  })

  it('其他公開站依名稱或語言叫出來，同樣先測再勾', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [TEST_SITES]: { body: { checks: [check('rutor')] } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    // 不搜就不列：八十幾站不該佔掉整頁。
    await screen.findByText('其他公開站')
    expect(screen.queryByTestId('others')).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('搜尋名稱'), 'to')
    const others = within(await screen.findByTestId('others'))
    expect(others.getAllByRole('checkbox')).toHaveLength(2)
    expect(others.getByRole('checkbox', { name: 'RuTor' })).toBeInTheDocument()
    expect(others.getByRole('checkbox', { name: 'Tokyo Toshokan' })).toBeInTheDocument()

    await user.clear(screen.getByLabelText('搜尋名稱'))
    await user.selectOptions(screen.getByRole('combobox', { name: '語言' }), '俄文（俄羅斯）')
    const russian = within(screen.getByTestId('others'))
    expect(russian.getAllByRole('checkbox')).toHaveLength(1)
    await user.click(russian.getByRole('button', { name: '測試 RuTor' }))
    await waitFor(() => expect(russian.getByRole('checkbox', { name: 'RuTor' })).toBeEnabled())
    expect(bodyOf(fetchStub, '/api/setup/indexers/test')).toEqual({ indexers: ['rutor'] })
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

  it('既有 Prowlarr 的站數也讀頁上的清單：測試之後使用者自己加的站照樣算（berth-lab 實測）', async () => {
    const existingProwlarr = chosen({
      kind: 'prowlarr',
      origin: 'existing',
      base_url: 'http://nas:9696',
      reason: 'connected',
      detail: '0',
    })
    stubApi({
      [STATUS]: {
        body: setupStatus({
          ...AT_INDEXER,
          services: [...ALL_BUNDLED.slice(0, 2), existingProwlarr],
        }),
      },
      [INDEXERS]: {
        body: indexerSetup({
          origin: 'existing',
          base_url: 'http://nas:9696',
          sites: [site(RECOMMENDED[1], 1), site(RECOMMENDED[6], 2)],
          candidates: [],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    const berth = within((await screen.findByText('BTH 4')).closest('li')!)
    expect(await berth.findByText('既有 · Prowlarr · 2 個索引站')).toBeInTheDocument()
  })

  it('已加入的站可以一站一站搜，也可以全部搜；一站失敗不影響其他站', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: withSites() },
      [`${SEARCH}?query=Frieren&indexer_id=1`]: {
        body: {
          query: 'Frieren',
          error: '',
          sites: [siteSearch(1, 'dmhy', 12, ['[LoliHouse] Frieren - 28', 'b', 'c'])],
        },
      },
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
    const added = within(await screen.findByTestId('added'))
    // 還沒按之前，加進來的每一站都在清單上，說它還沒搜。
    expect(added.getAllByText('還沒搜')).toHaveLength(3)
    await user.type(added.getByLabelText('關鍵字'), 'Frieren')

    await user.click(added.getByRole('button', { name: '搜尋 dmhy' }))
    expect(await added.findByText('12 筆')).toBeInTheDocument()
    expect(added.getAllByText('還沒搜')).toHaveLength(2)

    await user.click(added.getByRole('button', { name: '搜尋全部' }))
    expect(await added.findByText('0 筆')).toBeInTheDocument()
    expect(added.getByText('[LoliHouse] Frieren - 28')).toBeInTheDocument()
    expect(added.getByText('搜尋失敗')).toBeInTheDocument()
    expect(added.getByText('GET /api/v1/search: 502 Bad Gateway')).not.toBeVisible()
    const searches = fetchStub.mock.calls.filter(([url]) =>
      String(url).includes('/indexers/search'),
    )
    expect(searches.map(([url]) => String(url))).toEqual([
      '/api/setup/indexers/search?query=Frieren&indexer_id=1',
      '/api/setup/indexers/search?query=Frieren',
    ])
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

  it('在 Prowlarr 停用的站說它停用了，不給搜尋：搜尋不會問它（berth-lab 實測）', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: {
        body: indexerSetup({
          sites: [site(RECOMMENDED[1], 1), site({ ...OTHER_PUBLIC[0], enabled: false }, 4)],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    const off = within(await screen.findByRole('article', { name: 'Knaben' }))
    expect(off.getByText('在 Prowlarr 停用了')).toBeInTheDocument()
    expect(off.queryByRole('button', { name: '搜尋 Knaben' })).not.toBeInTheDocument()
    expect(off.queryByText('還沒搜')).not.toBeInTheDocument()
  })

  it('要帳號的站（在 Prowlarr 自己加的）列在已加入、可以搜，但沒有移除', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: {
        body: indexerSetup({
          sites: [
            site(RECOMMENDED[1], 1),
            site(
              {
                definition_name: 'AnimeBytes',
                name: 'AnimeBytes',
                privacy: 'private',
                removable: false,
              },
              7,
            ),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    const mine = within(await screen.findByRole('article', { name: 'AnimeBytes' }))
    expect(mine.getByRole('button', { name: '搜尋 AnimeBytes' })).toBeInTheDocument()
    expect(mine.queryByRole('button', { name: '移除' })).not.toBeInTheDocument()
    expect(mine.getByText('要帳號的站 Berth 不移除')).toBeInTheDocument()
  })

  it('既有 Prowlarr：列出它已有的站、可以試搜、沒有移除；加站寫明加進你的 Prowlarr（M4 票 20）', async () => {
    const existingProwlarr = chosen({
      kind: 'prowlarr',
      origin: 'existing',
      base_url: 'http://nas:9696',
      reason: 'connected',
      detail: '2',
    })
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({
          ...AT_INDEXER,
          services: [...ALL_BUNDLED.slice(0, 2), existingProwlarr],
        }),
      },
      [INDEXERS]: {
        body: indexerSetup({
          origin: 'existing',
          base_url: 'http://nas:9696',
          web_ui_login: false,
          web_port: null,
          sites: [
            site({ ...RECOMMENDED[0], removable: false }, 1),
            site({ definition_name: 'AnimeBytes', name: 'AnimeBytes', removable: false }, 2),
          ],
          candidates: RECOMMENDED.slice(1),
          steps: [step('prowlarr', 'ok', '2')],
        }),
      },
      [`${SEARCH}?query=`]: {
        body: {
          query: '',
          error: '',
          sites: [siteSearch(1, 'Nyaa.si', 5, ['x']), siteSearch(2, 'AnimeBytes', 3, ['y'])],
        },
      },
      [TEST_SITES]: { body: { checks: [check('dmhy')] } },
      [ADD_INDEXERS]: {
        body: indexerSetup({
          origin: 'existing',
          base_url: 'http://nas:9696',
          web_ui_login: false,
          web_port: null,
          steps: [step('prowlarr', 'ok', '3'), step('dmhy', 'ok')],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    const added = within(await screen.findByTestId('added'))
    expect(added.getByText('2 站')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Nyaa.si' })).not.toBeInTheDocument()
    expect(added.queryByRole('button', { name: '移除' })).not.toBeInTheDocument()
    // 介面登入只屬於套件內。
    expect(screen.queryByTestId('prowlarr-login')).not.toBeInTheDocument()
    // 要移除它的站到它自己的介面：連結是使用者填的位址。
    expect(added.getByRole('link', { name: '開啟 Prowlarr 的索引站頁' })).toHaveAttribute(
      'href',
      'http://nas:9696/#/indexers',
    )

    await user.click(added.getByRole('button', { name: '搜尋全部' }))
    expect(await added.findByText('5 筆')).toBeInTheDocument()
    expect(added.getByText('3 筆')).toBeInTheDocument()
    // 試搜不寫任何東西；沒按「加入」就什麼都沒加。
    expect(fetchStub.mock.calls.every(([, init]) => (init?.method ?? 'GET') === 'GET')).toBe(true)

    // 加站：同一套先測再勾，按鈕旁寫明加進哪一台、加哪幾站。
    await user.click(screen.getByRole('button', { name: '測試 dmhy' }))
    const dmhy = screen.getByRole('checkbox', { name: 'dmhy' })
    await waitFor(() => expect(dmhy).toBeEnabled())
    expect(screen.queryByTestId('adds-into')).not.toBeInTheDocument()
    await user.click(dmhy)
    expect(screen.getByTestId('adds-into')).toHaveTextContent(
      '按下去會把這 1 站加進你的 Prowlarr（nas:9696）：dmhy。',
    )
    await user.click(screen.getByRole('button', { name: '加入 1 個站' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/indexers/apply')).toEqual({ indexers: ['dmhy'] })
  })

  it('既有 Prowlarr 一站都沒有：待處理、說出下一步，「重新讀取」重測那一台（M4 票 20）', async () => {
    const empty = chosen({
      kind: 'prowlarr',
      origin: 'existing',
      base_url: 'http://host.docker.internal:48696',
      reason: 'connected',
      detail: '0',
    })
    const status = setupStatus({ ...AT_INDEXER, services: [...ALL_BUNDLED.slice(0, 2), empty] })
    const fetchStub = stubApi({
      [STATUS]: { body: status },
      [INDEXERS]: {
        body: indexerSetup({
          origin: 'existing',
          base_url: 'http://host.docker.internal:48696',
          web_ui_login: false,
          web_port: null,
          sites: [],
          steps: [step('prowlarr', 'pending', '0')],
        }),
      },
      [RETEST_PROWLARR]: { body: status },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    const notice = within(await screen.findByTestId('no-sites'))
    expect(notice.getByText('待處理')).toBeInTheDocument()
    expect(notice.getByText(/Berth 什麼都搜不到/)).toBeInTheDocument()
    // 連結用瀏覽器開得了的位址：host.docker.internal 換成瀏覽器現在的主機名。
    expect(notice.getByRole('link', { name: '開啟 Prowlarr 的索引站頁' })).toHaveAttribute(
      'href',
      `http://${window.location.hostname}:48696/#/indexers`,
    )
    // 「已加入」那一段不畫空的；加站那一段照樣在，「之後再說」在它旁邊。
    expect(screen.queryByTestId('added')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: '加站' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '之後再說' })).toBeInTheDocument()
    // 還沒完：沒有「前往下一個泊位」。
    expect(screen.queryByRole('button', { name: '前往下一個泊位' })).not.toBeInTheDocument()

    await user.click(notice.getByRole('button', { name: '重新讀取' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/services/prowlarr/test')).toBe(true))
    expect(bodyOf(fetchStub, '/api/setup/services/prowlarr/test')).toEqual({ restart: true })
  })

  it('既有 Prowlarr 這一次讀不到清單：說讀不到，不說成沒有站（M4 票 20）', async () => {
    const existing = chosen({
      kind: 'prowlarr',
      origin: 'existing',
      base_url: 'http://nas:9696',
      reason: 'connected',
      detail: '2',
    })
    stubApi({
      [STATUS]: {
        body: setupStatus({ ...AT_INDEXER, services: [...ALL_BUNDLED.slice(0, 2), existing] }),
      },
      [INDEXERS]: {
        body: indexerSetup({
          origin: 'existing',
          base_url: 'http://nas:9696',
          web_ui_login: false,
          web_port: null,
          sites: [],
          candidates: [],
          steps: [step('prowlarr', 'ok', '2')],
          error: 'GET /api/v1/indexer/schema: 503',
        }),
      },
    })

    renderWithProviders(<SetupPage />)

    const failed = within(await screen.findByTestId('read-failed'))
    expect(failed.getByText(/讀不到這一台 Prowlarr 的站清單/)).toBeInTheDocument()
    expect(failed.getByText('GET /api/v1/indexer/schema: 503')).toBeInTheDocument()
    expect(failed.getByRole('button', { name: '重新讀取' })).toBeInTheDocument()
    expect(screen.queryByTestId('no-sites')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '加站' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '之後再說' })).toBeInTheDocument()
  })

  it('剛選下去、清單還沒重讀回來：不閃另一種來源的文案（M4 票 20）', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      // 清單還是選之前的那一份：來源是空的。
      [INDEXERS]: { body: indexerSetup({ origin: null, sites: [], candidates: [] }) },
    })

    renderWithProviders(<SetupPage />)

    await screen.findByText(/先測試，通過的站勾起來加入/)
    expect(screen.queryByText(/你那一台上已經有的站/)).not.toBeInTheDocument()
    expect(screen.queryByTestId('added')).not.toBeInTheDocument()
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
      candidates: [],
      steps: [step('torznab', 'ok', 'Jackett · TV')],
    })
    const fetchStub = stubApi({
      // 接上就是選了既有：之後重讀的精靈狀態裡有這一台。
      [STATUS]: () => ({
        body: connectedYet
          ? setupStatus({ ...AT_INDEXER, services: [...ALL_BUNDLED.slice(0, 2), existingProwlarr] })
          : CHOOSING_INDEXER,
      }),
      [INDEXERS]: { body: indexerSetup({ origin: 'existing', base_url: '', candidates: [] }) },
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

    await user.click(await screen.findByRole('button', { name: '搜尋全部' }))
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
    await screen.findByTestId('recommended')
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
  return indexerSetup({
    sites: [site(RECOMMENDED[1], 1), site(RECOMMENDED[4], 2), site(RECOMMENDED[6], 3)],
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
      body: indexerSetup({ sites: [site(RECOMMENDED[1], 1), site(RECOMMENDED[4], 2)] }),
    },
  })
}

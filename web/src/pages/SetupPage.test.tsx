import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import { ALL_BUNDLED, detection, setupStatus } from '../test/fixtures'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const STATUS = 'GET /api/setup/status'
const ADMIN = 'POST /api/setup/admin'
const DETECT = 'POST /api/setup/detect'

function bodyOf(call: Parameters<typeof fetch>): unknown {
  const init = call[1]
  return JSON.parse(String(init?.body))
}

describe('精靈的外框', () => {
  /** 票 03 第 13 條：精靈本來一個標題都沒有，每一步的 `<h2>` 底下沒有 h1 撐著。 */
  it('精靈有唯一的 h1，每一步的標題掛在它底下', async () => {
    stubApi({ [STATUS]: { body: setupStatus() } })

    renderWithProviders(<SetupPage />)

    // 先等這一步畫出來：外框的 h1 在讀取中就在了，步驟的 h2 要等狀態回來。
    expect(await screen.findByRole('heading', { level: 2 })).toBeVisible()
    expect(screen.getByRole('heading', { level: 1, name: '設定精靈' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })
})

describe('第 1 步：建立管理員', () => {
  it('剖面跟著輸入走，套用前後看同一份「將會寫入」', async () => {
    stubApi({ [STATUS]: { body: setupStatus() } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('帳號'), 'skipper')

    // Berth 管理員一列、Jellyfin 與兩個介面三列都跟著顯示同一個帳號（逐狀態的文案在
    // `AdminStep.test.tsx`）。
    expect(screen.getAllByText(/^skipper/)).toHaveLength(4)
  })

  it('取消勾選之後 qBittorrent 與 Prowlarr 那兩列顯示不套用', async () => {
    stubApi({ [STATUS]: { body: setupStatus() } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('帳號'), 'skipper')
    await user.click(screen.getByRole('checkbox'))

    expect(screen.getAllByText('不套用')).toHaveLength(2)
  })

  it('送出時帶上帳密與勾選狀態', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus() },
      [ADMIN]: { body: setupStatus({ admin_created: true, admin_username: 'skipper' }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/admin')
      expect(call && bodyOf(call)).toEqual({
        username: 'skipper',
        password: 'harbour',
        apply_to_services: true,
      })
    })
  })

  it('非 GET 帶 X-Requested-With 作 CSRF 防線', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus() },
      [ADMIN]: { body: setupStatus({ current_step: 2, admin_created: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/admin')
      const headers = call?.[1]?.headers as Record<string, string>
      expect(headers['X-Requested-With']).toBe('XMLHttpRequest')
    })
  })

  it('空白欄位就地報錯，不打後端', async () => {
    const fetchStub = stubApi({ [STATUS]: { body: setupStatus() } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立管理員' }))

    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0)
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/admin')).toBe(false)
  })

  it('後端存不進去時說得出下一步', async () => {
    stubApi({
      [STATUS]: { body: setupStatus() },
      [ADMIN]: { status: 500, body: { detail: 'boom' } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員' }))

    expect(await screen.findByText(/確認容器狀態/)).toBeInTheDocument()
  })
})

describe('第 2 步：偵測服務', () => {
  const AT_STEP_TWO = setupStatus({
    current_step: 2,
    admin_created: true,
    admin_username: 'skipper',
  })

  it('每個服務逐條顯示判定與實測值', async () => {
    stubApi({
      [STATUS]: { body: AT_STEP_TWO },
      [DETECT]: { body: setupStatus({ ...AT_STEP_TWO, current_step: 3, services: ALL_BUNDLED }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始探測' }))

    // 伺服器已經把步驟推到 3，但畫面停在這一輪的結果上等使用者按下前進。
    const sequence = await screen.findByTestId('mooring-sequence')
    await waitFor(() => {
      expect(within(sequence).getAllByText('套件內')).toHaveLength(3)
    })
    expect(within(sequence).getByText('12.1.0')).toBeInTheDocument()
    expect(within(sequence).getByText('v5.2.3 · Web API 2.15.1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '前往泊位 1' })).toBeInTheDocument()
  })

  it('判定理由逐服務寫出來，不是「連線失敗」了事', async () => {
    stubApi({
      [STATUS]: { body: AT_STEP_TWO },
      [DETECT]: { body: setupStatus({ ...AT_STEP_TWO, services: ALL_BUNDLED }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始探測' }))

    expect(await screen.findByText(/初始精靈尚未跑過/)).toBeInTheDocument()
    expect(await screen.findByText(/免密進得去/)).toBeInTheDocument()
    expect(await screen.findByText(/一個索引站都沒有/)).toBeInTheDocument()
  })

  it('泊位板把三個判定點亮，沒有服務判定的兩格（媒體庫路徑、TMDB）仍是未指派', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services: ALL_BUNDLED }) },
    })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })

    await waitFor(() => expect(within(board).getAllByText('套件內')).toHaveLength(3))
    expect(within(board).getAllByText('未指派')).toHaveLength(2)
  })

  it('既有服務就地展開連線表單', async () => {
    const existing = [
      detection({ origin: 'existing', reason: 'setup_completed', detail: '12.0.0' }),
      ...ALL_BUNDLED.slice(1),
    ]
    stubApi({ [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services: existing }) } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByLabelText('位址')).toHaveValue('http://jellyfin:8096')
    expect(screen.getByRole('button', { name: '測試連線' })).toBeInTheDocument()
  })

  it('從 COMPOSE_PROFILES 拿掉的服務判為既有，並附可複製的手動步驟', async () => {
    const removed = [
      detection({ origin: 'existing', reason: 'not_deployed', detail: '', resolved: false }),
      ...ALL_BUNDLED.slice(1),
    ]
    stubApi({ [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services: removed }) } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText(/主機名解不到/)).toBeInTheDocument()
    expect(screen.getByText('COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr')).toBeInTheDocument()
    const board = await screen.findByRole('region', { name: '泊位板' })
    await waitFor(() => expect(within(board).getAllByText('套件內')).toHaveLength(2))
    expect(within(board).getByText('既有')).toBeInTheDocument()
  })

  it('既有服務連得上就不再是「待你處理」，連不上才是', async () => {
    const services = [
      // 連得上：判定是服務自己報的事實（跑過初始精靈）。
      detection({ origin: 'existing', reason: 'setup_completed', detail: '12.0.0' }),
      // 連不上：要使用者補連線資訊。
      detection({
        kind: 'qbittorrent',
        origin: 'existing',
        reason: 'auth_required',
        detail: '',
        resolved: false,
      }),
      ALL_BUNDLED[2],
    ]
    stubApi({ [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services }) } })

    renderWithProviders(<SetupPage />)
    const sequence = await screen.findByTestId('mooring-sequence')
    const lines = await within(sequence).findAllByRole('listitem')

    // 纜繩是逐條繫上的，兩條都要等它輪到。
    await waitFor(() => expect(within(lines[0]).getByText('既有')).toHaveClass('bg-secured'))
    await waitFor(() => expect(within(lines[1]).getByText('既有')).toHaveClass('bg-assigned'))
    // 兩條都給表單（票 05 驗收：既有就顯示連線表單）。
    expect(within(lines[0]).getByRole('button', { name: '測試連線' })).toBeInTheDocument()
    expect(within(lines[1]).getByRole('button', { name: '測試連線' })).toBeInTheDocument()
  })

  it('貼上的 Prowlarr API key 送到 connect 端點', async () => {
    const noKey = [
      ...ALL_BUNDLED.slice(0, 2),
      detection({
        kind: 'prowlarr',
        origin: 'existing',
        reason: 'api_key_missing',
        detail: '',
        base_url: 'http://prowlarr:9696',
        resolved: false,
      }),
    ]
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services: noKey }) },
      'POST /api/setup/services/prowlarr': {
        body: setupStatus({ ...AT_STEP_TWO, services: ALL_BUNDLED }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('API key'), 'pasted-key')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/services/prowlarr')
      expect(call && bodyOf(call)).toMatchObject({
        base_url: 'http://prowlarr:9696',
        api_key: 'pasted-key',
      })
    })
  })

  it('服務還在啟動時顯示等待狀態與上限', async () => {
    const starting = [
      ALL_BUNDLED[0],
      detection({ kind: 'qbittorrent', origin: 'pending', reason: 'unreachable', detail: '' }),
      ALL_BUNDLED[2],
    ]
    stubApi({
      [STATUS]: {
        body: setupStatus({ ...AT_STEP_TWO, services: starting, waited_seconds: 12 }),
      },
      [DETECT]: {
        body: setupStatus({ ...AT_STEP_TWO, services: starting, waited_seconds: 15 }),
      },
    })

    renderWithProviders(<SetupPage />)

    // 倒數貼在還在等的那一條纜繩上，不是清單底下的一條橫幅。
    const sequence = await screen.findByTestId('mooring-sequence')
    const line = within(sequence).getAllByRole('listitem')[1]
    expect(await within(line).findByText('12 / 120 秒')).toBeInTheDocument()
    expect(within(line).getByText('探測中')).toBeInTheDocument()
  })

  /**
   * 票 06g：四個容器同時起來時，探測本身會失敗（Jellyfin 啟動中的 503 冒成 500）。
   * 那時候還沒有任何判定，只看「有沒有服務在等」的話永遠不會再探，畫面停在「探測沒跑完」。
   */
  it('探測本身失敗時照樣排下一次，不必按重新探測', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    const fetchStub = stubApi({
      [STATUS]: { body: AT_STEP_TWO },
      [DETECT]: () => {
        calls += 1
        return calls === 1
          ? { status: 500, body: { detail: 'Internal Server Error' } }
          : { body: setupStatus({ ...AT_STEP_TWO, services: ALL_BUNDLED }) }
      },
    })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始探測' }))
    await waitFor(() =>
      expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/detect')).toBe(true),
    )
    // 視窗內的失敗是「還在探測」，不是一句要人去查後端的失敗。
    expect(screen.getByRole('button', { name: '探測中…' })).toBeInTheDocument()
    expect(screen.queryByText(/探測沒跑完/)).not.toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(3000)

    expect(await screen.findByRole('button', { name: '前往泊位 1' })).toBeInTheDocument()
    const detects = fetchStub.mock.calls.filter(([url]) => url === '/api/setup/detect')
    expect(detects).toHaveLength(2)
  })

  it('探測一直失敗，過了輪詢上限就停下來等人按', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetchStub = stubApi({
      [STATUS]: { body: AT_STEP_TWO },
      [DETECT]: { status: 500, body: { detail: 'Internal Server Error' } },
    })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '開始探測' }))
    await vi.advanceTimersByTimeAsync(AT_STEP_TWO.window_seconds * 1000 + 10_000)
    const stopped = fetchStub.mock.calls.filter(([url]) => url === '/api/setup/detect').length
    await vi.advanceTimersByTimeAsync(30_000)

    expect(fetchStub.mock.calls.filter(([url]) => url === '/api/setup/detect')).toHaveLength(
      stopped,
    )
    expect(stopped).toBeGreaterThan(2)
    expect(screen.getByText(/探測沒跑完/)).toBeInTheDocument()
  })

  /** 票 06g code review：放棄之後 `detect` 的失敗還掛著，不能蓋掉單一服務重探拿回來的新判定。 */
  it('放棄之後重新偵測一個服務拿回探測中，輪詢照樣恢復', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const timedOut = [
      ALL_BUNDLED[0],
      detection({
        kind: 'qbittorrent',
        origin: 'timeout',
        reason: 'starting',
        detail: '',
        resolved: false,
      }),
      ALL_BUNDLED[2],
    ]
    const starting = timedOut.map((row) =>
      row.kind === 'qbittorrent' ? { ...row, origin: 'pending' as const } : row,
    )
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus({ ...AT_STEP_TWO, services: timedOut }) },
      [DETECT]: { status: 500, body: { detail: 'Internal Server Error' } },
    })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '重試' }))
    await vi.advanceTimersByTimeAsync(AT_STEP_TWO.window_seconds * 1000 + 10_000)
    expect(await screen.findByText(/探測沒跑完/)).toBeInTheDocument()
    // 使用者只重探 qBittorrent：它回探測中，之後的整輪探測也好了。
    let polled = 0
    fetchStub.mockImplementation(async (input, init) => {
      const url = String(input)
      if (init?.method === 'POST' && url === '/api/setup/detect') {
        const body = JSON.parse(String(init.body)) as { kind?: string }
        if (!body.kind) polled += 1
        const services = body.kind ? starting : ALL_BUNDLED
        return new Response(JSON.stringify(setupStatus({ ...AT_STEP_TWO, services })))
      }
      return new Response(JSON.stringify(setupStatus({ ...AT_STEP_TWO, services: timedOut })))
    })

    await user.click(screen.getByRole('button', { name: '重新偵測這個服務（qBittorrent）' }))
    await vi.advanceTimersByTimeAsync(3000)

    await waitFor(() => expect(polled).toBeGreaterThan(0))
    expect(screen.queryByText(/探測沒跑完/)).not.toBeInTheDocument()
  })

  it('逾時之後給重試與可複製的診斷指令', async () => {
    const timedOut = [
      ALL_BUNDLED[0],
      detection({
        kind: 'qbittorrent',
        origin: 'timeout',
        reason: 'unreachable',
        detail: '',
        resolved: false,
      }),
      ALL_BUNDLED[2],
    ]
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({ ...AT_STEP_TWO, services: timedOut, waited_seconds: 121 }),
      },
      [DETECT]: { body: setupStatus({ ...AT_STEP_TWO, services: ALL_BUNDLED }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    expect(await screen.findByText('docker compose ps qbittorrent')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '重試' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/detect')
      expect(call && bodyOf(call)).toEqual({ restart: true })
    })
  })

  /** 前置列的管理員那一格就是回第 1 步的入口（票 06d：「改帳密」回到第 1 步上）。 */
  it('可以回頭改管理員帳密', async () => {
    stubApi({ [STATUS]: { body: AT_STEP_TWO } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: /管理員已建立：skipper/ }))

    expect(screen.getByRole('button', { name: '建立管理員' })).toBeInTheDocument()
  })
})

describe('語言', () => {
  it('ZH / EN 切換整頁文案', async () => {
    stubApi({ [STATUS]: { body: setupStatus() } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: 'EN' }))

    expect(await screen.findByText('Create the Berth administrator')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })
})

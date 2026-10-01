import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import { ALL_BUNDLED, chosen, jellyfinSetup, setupStatus } from '../test/fixtures'
import { SetupPage } from './SetupPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const STATUS = 'GET /api/setup/status'
const OWNER = 'POST /api/setup/owner'
const CHOOSE = 'POST /api/setup/services/jellyfin'
const RETEST = 'POST /api/setup/services/jellyfin/test'

type FetchStub = ReturnType<typeof stubApi>

/** 打到某一支的每一次呼叫的 body。 */
function bodiesOf(stub: FetchStub, url: string): unknown[] {
  return stub.mock.calls
    .filter(([called]) => called === url)
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
}

/** `<method> <path>` 的形狀，與 `stubApi` 的 key 同一種寫法。 */
function requestsOf(stub: FetchStub): string[] {
  return stub.mock.calls.map(([url, init]) => `${init?.method ?? 'GET'} ${String(url)}`)
}

/** 二選一的那兩格。label 裡還有說明句與位址，所以只比開頭。 */
const bundledCard = () => screen.getByRole('radio', { name: /^套件內/ })
const existingCard = () => screen.getByRole('radio', { name: /^既有/ })

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

  /**
   * critique（票 15，DESIGN 三重編碼）：狀態字原本換成了來源，紅格與綠格都寫「套件內」，
   * 螢幕閱讀器念不出哪一台連不上。狀態字跟著信號，來源放進詳情列。
   */
  it('泊位板的狀態字跟著信號、來源寫在詳情列；還沒選的服務與沒有服務的格子是未指派', async () => {
    stubApi({
      [STATUS]: {
        body: setupStatus({
          current_step: 2,
          owner: 'skipper',
          services: [
            ALL_BUNDLED[0]!,
            chosen({ kind: 'qbittorrent', state: 'failed', reason: 'unreachable', detail: '' }),
          ],
        }),
      },
    })

    renderWithProviders(<SetupPage />)
    const board = await screen.findByRole('region', { name: '泊位板' })
    const slot = (code: string) => within(board).getByText(code).closest('li')!

    await waitFor(() => expect(slot('BTH 2')).toHaveTextContent('失敗'))
    expect(slot('BTH 2')).toHaveTextContent('套件內')
    expect(slot('BTH 1')).toHaveTextContent(/套件內 · 版本/)
    expect(slot('BTH 1')).not.toHaveTextContent('失敗')
    // 媒體庫與路徑、還沒選的 Prowlarr、TMDB。
    expect(within(board).getAllByText('未指派')).toHaveLength(3)
  })
})

describe('頁 1：Jellyfin 與擁有者', () => {
  const BUNDLED_JELLYFIN = chosen()
  const EXISTING_JELLYFIN = chosen({
    origin: 'existing',
    base_url: 'http://nas:8096',
    reason: 'setup_completed',
    detail: '12.0.0',
  })
  /** 選了套件內、連上了、還沒跑過初始精靈：建立管理員。 */
  const FOUND = setupStatus({ services: [BUNDLED_JELLYFIN] })

  async function fill(user: ReturnType<typeof userEvent.setup>, confirm = 'harbour') {
    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    if (confirm) await user.type(screen.getByLabelText('再輸入一次密碼'), confirm)
  }

  /** M4 票 15 驗收：不預選、不偵測。打開精靈只讀自己的狀態，一個服務都不去連。 */
  it('進頁與選擇之前只讀精靈狀態，不對任何服務發請求', async () => {
    const fetchStub = stubApi({ [STATUS]: { body: setupStatus() } })

    renderWithProviders(<SetupPage />)

    expect(
      await screen.findByRole('heading', { level: 2, name: '先選 Jellyfin 是哪一台' }),
    ).toBeVisible()
    expect(bundledCard()).not.toBeChecked()
    expect(existingCard()).not.toBeChecked()
    expect(screen.queryByLabelText('Jellyfin 帳號')).not.toBeInTheDocument()
    // 套件內那一格說得出會連哪裡——後端給的 compose 位址，還沒連。
    expect(screen.getByText('http://jellyfin:8096')).toBeInTheDocument()
    expect(new Set(requestsOf(fetchStub))).toEqual(new Set([STATUS]))
  })

  it('點「套件內」就存下並測，連上了才給建立管理員的表單', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus() },
      [CHOOSE]: { body: FOUND },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 Jellyfin 是哪一台' })
    await user.click(bundledCard())

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin')).toEqual([{ origin: 'bundled' }]),
    )
    expect(
      await screen.findByRole('heading', { level: 2, name: '建立 Jellyfin 管理員' }),
    ).toBeVisible()
    expect(screen.getByText('連上了')).toBeInTheDocument()
    // 說清楚 Berth 沒有自己的帳號、之後拿什麼登入（brief §11、§19 2026-09-26）。
    expect(screen.getByText(/Berth 沒有自己的帳號/)).toBeVisible()
    expect(screen.getByLabelText('再輸入一次密碼')).toBeInTheDocument()
  })

  it('點「既有」只展開表單不送出，按「測試連線」才送位址；那一台有管理員就是登入', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: setupStatus() },
      [CHOOSE]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 Jellyfin 是哪一台' })
    await user.click(existingCard())

    const address = screen.getByRole('textbox', { name: '位址' })
    expect(address).toHaveAttribute('placeholder', 'http://192.168.1.10:8096')
    // 選了既有，就說出套件內那一台怎麼從 compose 拿掉。
    expect(screen.getByText('COMPOSE_PROFILES=qbittorrent,prowlarr')).toBeInTheDocument()
    expect(requestsOf(fetchStub).some((request) => request.startsWith('POST'))).toBe(false)

    await user.type(address, 'http://nas:8096')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin')).toEqual([
        {
          origin: 'existing',
          base_url: 'http://nas:8096',
          api_key: '',
          username: '',
          password: '',
        },
      ]),
    )
    expect(
      await screen.findByRole('heading', { level: 2, name: '用你的 Jellyfin 管理員登入' }),
    ).toBeVisible()
    expect(screen.queryByLabelText('再輸入一次密碼')).not.toBeInTheDocument()
    expect(screen.getByText('不改這台 Jellyfin 的任何設定')).toBeInTheDocument()
  })

  it('連上既有的那一台之後位址表單收起來，測試那一條寫的是使用者填的那一台，要改再打開', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    expect(await screen.findByLabelText('Jellyfin 帳號')).toBeInTheDocument()
    expect(existingCard()).toBeChecked()
    expect(screen.queryByRole('button', { name: '測試連線' })).not.toBeInTheDocument()
    // 測試那一條寫的是使用者填的那一台，不是 compose 主機名。
    expect(screen.getByText('nas:8096/System/Info/Public')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '改位址' }))
    expect(screen.getByRole('textbox', { name: '位址' })).toHaveValue('http://nas:8096')
  })

  /** audit（票 15）：原本一送出就清掉 draft，請求還在路上時表單卸下、兩格都沒勾、焦點掉回標題。 */
  it('送出既有之後、回應回來之前：表單與勾選都留著，按鈕說測試中', async () => {
    let answer: (route: { body: unknown }) => void = () => {}
    stubApi({
      [STATUS]: { body: setupStatus() },
      [CHOOSE]: () => new Promise((resolve) => (answer = resolve)),
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 Jellyfin 是哪一台' })
    await user.click(existingCard())
    await user.type(screen.getByRole('textbox', { name: '位址' }), 'http://nas:8096')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    expect(await screen.findByRole('button', { name: '測試中…' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '位址' })).toHaveValue('http://nas:8096')
    expect(existingCard()).toBeChecked()

    answer({ body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) })
    expect(await screen.findByLabelText('Jellyfin 帳號')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '測試連線' })).not.toBeInTheDocument()
  })

  /** audit（票 15）：按鈕自己卸下之後，焦點原本交給 StepFrame 的兜底，越過剛打開的表單。 */
  it('按「改位址」之後焦點進到位址欄', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '改位址' }))

    expect(screen.getByRole('textbox', { name: '位址' })).toHaveFocus()
  })

  /**
   * audit（票 15，WCAG 4.1.3）：測試那一條跟結果一起掛上，第一次的結果念不出來；重測結果一樣時文字
   * 沒變，也念不出來。宣告區一直都在，測試中清空、有結果再寫。
   */
  it('測試結果由一直都在的宣告區說出來，重測結果一樣也再說一次', async () => {
    let answer: (route: { body: unknown }) => void = () => {}
    const DOWN = setupStatus({
      services: [chosen({ state: 'failed', reason: 'unreachable', detail: '' })],
    })
    stubApi({
      [STATUS]: { body: setupStatus() },
      [CHOOSE]: { body: DOWN },
      [RETEST]: () => new Promise((resolve) => (answer = resolve)),
    })
    const user = userEvent.setup()
    const announcer = () => document.querySelector('[data-announcer="jellyfin"]')

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 Jellyfin 是哪一台' })
    expect(announcer()).toHaveAttribute('role', 'status')
    expect(announcer()).toHaveTextContent(/^$/)

    await user.click(bundledCard())
    await waitFor(() =>
      expect(announcer()).toHaveTextContent('Jellyfin 沒通過：主機名解得到但連不上'),
    )

    await user.click(screen.getByRole('button', { name: '重新測試' }))
    await waitFor(() => expect(announcer()).toHaveTextContent(/^$/))
    answer({ body: DOWN })
    await waitFor(() =>
      expect(announcer()).toHaveTextContent('Jellyfin 沒通過：主機名解得到但連不上'),
    )
  })

  it('套件內那一台的管理員已經建好時也是登入', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ services: [BUNDLED_JELLYFIN], owner_signs_in: true }) },
    })

    renderWithProviders(<SetupPage />)

    expect(
      await screen.findByRole('heading', { level: 2, name: '用你的 Jellyfin 管理員登入' }),
    ).toBeVisible()
    expect(screen.queryByLabelText('再輸入一次密碼')).not.toBeInTheDocument()
  })

  it('套件內的主機名解不到時說出 COMPOSE_PROFILES 的補法，「重新測試」重算上限', async () => {
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({
          services: [chosen({ state: 'failed', reason: 'not_deployed', detail: '' })],
        }),
      },
      [RETEST]: { body: FOUND },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('沒通過')).toBeInTheDocument()
    expect(screen.getByText('主機名解不到')).toBeInTheDocument()
    expect(screen.getByText(/jellyfin 的容器沒在跑.*或它不在這套 compose 裡/)).toBeInTheDocument()
    expect(screen.getByText('COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr')).toBeInTheDocument()
    expect(screen.getByText('docker compose up -d')).toBeInTheDocument()
    // 連不上就還沒有擁有者表單可填。
    expect(screen.queryByLabelText('Jellyfin 帳號')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '重新測試' }))

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin/test')).toEqual([{ restart: true }]),
    )
    expect(
      await screen.findByRole('heading', { level: 2, name: '建立 Jellyfin 管理員' }),
    ).toBeVisible()
  })

  /** 改了 `.env` 的 port 之後，重新測試只敲存下的那一條；再點一次套件內才重存 compose 位址。 */
  it('套件內紅著時再點一次套件內：重新選（重存位址再測），綠著時不重送', async () => {
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({
          services: [chosen({ state: 'failed', reason: 'not_deployed', detail: '' })],
        }),
      },
      [CHOOSE]: { body: FOUND },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('radio', { name: /^套件內/ }))

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin')).toEqual([{ origin: 'bundled' }]),
    )
    expect(
      await screen.findByRole('heading', { level: 2, name: '建立 Jellyfin 管理員' }),
    ).toBeVisible()
    await user.click(bundledCard())
    expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin')).toHaveLength(1)
  })

  it('套件內那一台還在啟動：倒數貼在那一條上，每 3 秒自動重測、不重算上限', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const starting = (waited: number) =>
      setupStatus({
        services: [
          chosen({ state: 'waiting', reason: 'starting', detail: '', waited_seconds: waited }),
        ],
      })
    let polls = 0
    const fetchStub = stubApi({
      [STATUS]: { body: starting(12) },
      [RETEST]: () => {
        polls += 1
        return { body: polls === 1 ? starting(15) : FOUND }
      },
    })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByText('12 / 120 秒')).toBeInTheDocument()
    expect(screen.getByText('啟動中')).toBeInTheDocument()
    expect(polls).toBe(0)

    await vi.advanceTimersByTimeAsync(3000)
    expect(await screen.findByText('15 / 120 秒')).toBeInTheDocument()
    expect(polls).toBe(1)

    await vi.advanceTimersByTimeAsync(3000)
    expect(
      await screen.findByRole('heading', { level: 2, name: '建立 Jellyfin 管理員' }),
    ).toBeVisible()

    // 有結論之後就不再測。輪詢不是使用者按的「重新測試」，所以不帶 restart。
    await vi.advanceTimersByTimeAsync(9000)
    expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin/test')).toEqual([
      { restart: false },
      { restart: false },
    ])
  })

  /** M4 票 23：別頁的服務在啟動中不跟著輪詢，它的重測只會與這一頁的命令搶同一組設定。 */
  it('只重測畫面上等著的那一個服務', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const waiting = { state: 'waiting', reason: 'starting', detail: '', waited_seconds: 3 } as const
    const both = setupStatus({
      current_step: 2,
      owner: 'skipper',
      services: [chosen(waiting), chosen({ ...waiting, kind: 'qbittorrent' })],
    })
    const fetchStub = stubApi({
      [STATUS]: { body: both },
      'POST /api/setup/services/qbittorrent/test': { body: both },
    })

    renderWithProviders(<SetupPage />)
    expect(await screen.findByText('3 / 120 秒')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(3000)
    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/services/qbittorrent/test')).toEqual([
        { restart: false },
      ]),
    )
    expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin/test')).toEqual([])
  })

  it('剖面說出會做什麼，也說出密碼不存下來', async () => {
    stubApi({ [STATUS]: { body: FOUND } })

    renderWithProviders(<SetupPage />)

    const cutaway = (await screen.findByText('將會做什麼')).closest('section')!
    expect(within(cutaway).getByText('Jellyfin 管理員')).toBeInTheDocument()
    expect(within(cutaway).getByText('API key「Berth」')).toBeInTheDocument()
    expect(within(cutaway).getByText('你的密碼（只交給 Jellyfin）')).toBeInTheDocument()
  })

  it('送出帳密到 /setup/owner，帶 CSRF 標頭；成立之後來源鎖住，停在結果上', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: FOUND },
      [OWNER]: {
        body: setupStatus({ current_step: 2, owner: 'skipper', services: [BUNDLED_JELLYFIN] }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user)
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    await waitFor(() => {
      const call = fetchStub.mock.calls.find(([url]) => url === '/api/setup/owner')
      // 套件內那一台不問語言與遠端存取：帶 UI 語言、不開（M4 票 18）。
      expect(call && JSON.parse(String(call[1]?.body))).toEqual({
        username: 'skipper',
        password: 'harbour',
        ui_culture: 'zh-TW',
        metadata_language: 'zh-TW',
        metadata_country: 'TW',
        remote_access: false,
      })
      const headers = call?.[1]?.headers as Record<string, string>
      expect(headers['X-Requested-With']).toBe('XMLHttpRequest')
    })
    // 成立之後停在結果上（票 06d 的規則），按了才走。
    expect(await screen.findByRole('heading', { level: 2, name: '擁有者：skipper' })).toBeVisible()
    // 擁有者是那一台上的帳號：來源鎖住，另一格按不動，說得出為什麼（M4 票 15）。
    expect(existingCard()).toBeDisabled()
    expect(bundledCard()).toBeChecked()
    expect(screen.getByText(/換一台等於換擁有者/)).toBeVisible()
    expect(screen.queryByLabelText('語言與地區')).toBeNull()

    await user.click(screen.getByRole('button', { name: '前往下一個泊位' }))
    expect(
      await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' }),
    ).toBeVisible()
  })

  it('建立時兩次密碼不一樣就地報錯，不打後端', async () => {
    const fetchStub = stubApi({ [STATUS]: { body: FOUND } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user, 'harbor')
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    expect(await screen.findByText('兩次輸入的密碼不一樣。')).toBeVisible()
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/owner')).toBe(false)
  })

  it('空白欄位就地報錯，不打後端', async () => {
    const fetchStub = stubApi({ [STATUS]: { body: FOUND } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '建立管理員並登入' }))

    expect(screen.getAllByText('帳號與密碼都要填。').length).toBeGreaterThan(0)
    expect(fetchStub.mock.calls.some(([url]) => url === '/api/setup/owner')).toBe(false)
  })

  it('不是管理員就地說明被拒的原因', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
      [OWNER]: { status: 403, body: { detail: { reason: 'not_administrator', detail: '' } } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user, '')
    await user.click(screen.getByRole('button', { name: '登入' }))

    expect(await screen.findByText(/不是管理員/)).toBeVisible()
  })

  it('Jellyfin 那一段沒做完時說出來，它的原文收進技術細節', async () => {
    stubApi({
      [STATUS]: { body: FOUND },
      [OWNER]: {
        status: 502,
        body: { detail: { reason: 'jellyfin_failed', detail: 'Jellyfin 10.11.11 is too old' } },
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user)
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    // 人話在上；Jellyfin 那一步的英文原文收進技術細節（M4 票 21）。
    expect(await screen.findByText(/^Jellyfin 那一段沒做完/)).toBeVisible()
    expect(screen.getByText('Jellyfin 10.11.11 is too old')).not.toBeVisible()
  })

  it('後端連不上時說得出下一步', async () => {
    stubApi({
      [STATUS]: { body: FOUND },
      [OWNER]: { status: 500, body: { detail: 'boom' } },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user)
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    expect(await screen.findByText(/後端出錯了/)).toBeInTheDocument()
  })

  /** 泊位板的第一格就是回頁 1 的入口（票 06d：走過的步驟點得回去）。 */
  it('回頭看頁 1：擁有者是誰、來源鎖住，沒有帳密表單', async () => {
    stubApi({
      [STATUS]: {
        body: setupStatus({ current_step: 2, owner: 'skipper', services: [BUNDLED_JELLYFIN] }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    // 讀取中的外框也有板，但格子還不是按鈕：先等頁 2 畫出來。
    await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
    const berth = screen.getByText('BTH 1').closest('li')!
    await user.click(within(berth).getByRole('button'))

    expect(await screen.findByRole('heading', { level: 2, name: '擁有者：skipper' })).toBeVisible()
    expect(screen.getByText(/之後登入 Berth 就用這個 Jellyfin 帳號/)).toBeVisible()
    // 回頭看的說明：這裡能做什麼、不能做的去哪裡（票 06d）。
    const revisit = screen.getByRole('note', { name: '回頭看' })
    // 只列畫面上真的有的動作（M4 票 18）：套件內這一格沒有「重新測試」鈕，也沒有「改位址」。
    expect(within(revisit).getByText(/看擁有者是誰/)).toBeVisible()
    expect(within(revisit).queryByText(/重新測試/)).toBeNull()
    expect(within(revisit).getByText(/Berth 不支援/)).toBeVisible()
    expect(screen.queryByRole('button', { name: '重新測試' })).toBeNull()
    expect(screen.queryByLabelText('Jellyfin 帳號')).not.toBeInTheDocument()
    expect(existingCard()).toBeDisabled()
    expect(screen.getByText(/換一台等於換擁有者/)).toBeVisible()
  })
})

describe('頁 1：替還沒初始化的既有 Jellyfin 建立擁有者（M4 票 18）', () => {
  const PENDING_EXISTING = setupStatus({
    services: [chosen({ origin: 'existing', base_url: 'http://nas:8096' })],
  })

  async function fill(user: ReturnType<typeof userEvent.setup>) {
    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.type(screen.getByLabelText('再輸入一次密碼'), 'harbour')
  }

  it('問語言與地區（預設跟著 UI 語言）與遠端存取（預設不開），送出的就是選的', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: PENDING_EXISTING },
      [OWNER]: { body: setupStatus({ current_step: 2, owner: 'skipper' }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await fill(user)
    const language = screen.getByRole('combobox', { name: '語言與地區' })
    const remote = screen.getByRole('checkbox', { name: '開啟遠端存取' })
    expect(language).toHaveDisplayValue('中文（台灣）')
    expect(remote).not.toBeChecked()
    expect(remote).toHaveAccessibleDescription(/用不到它/)

    await user.selectOptions(language, 'en-GB')
    await user.click(remote)
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/owner')).toEqual([
        {
          username: 'skipper',
          password: 'harbour',
          ui_culture: 'en-GB',
          metadata_language: 'en',
          metadata_country: 'GB',
          remote_access: true,
        },
      ]),
    )
  })

  it('已經有管理員的既有 Jellyfin 是登入：不問，也不送', async () => {
    const fetchStub = stubApi({
      [STATUS]: {
        body: setupStatus({
          services: [chosen({ origin: 'existing', reason: 'setup_completed' })],
          owner_signs_in: true,
        }),
      },
      [OWNER]: { body: setupStatus({ current_step: 2, owner: 'skipper' }) },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    expect(screen.queryByLabelText('語言與地區')).toBeNull()
    expect(screen.queryByLabelText('開啟遠端存取')).toBeNull()
    await user.click(screen.getByRole('button', { name: '登入' }))

    await waitFor(() =>
      expect(bodiesOf(fetchStub, '/api/setup/owner')).toEqual([
        { username: 'skipper', password: 'harbour' },
      ]),
    )
  })

  it('套件內還沒初始化的那一台不問', async () => {
    stubApi({ [STATUS]: { body: setupStatus({ services: [chosen()] }) } })

    renderWithProviders(<SetupPage />)

    expect(await screen.findByLabelText('Jellyfin 帳號')).toBeVisible()
    expect(screen.queryByLabelText('語言與地區')).toBeNull()
    expect(screen.queryByLabelText('開啟遠端存取')).toBeNull()
  })
})

describe('頁 1：擁有者成立之後 Berth 的 key 被撤了（M4 票 18）', () => {
  it('就地用管理員重新登入換 key，然後重新測試', async () => {
    const revoked = setupStatus({
      current_step: 2,
      owner: 'skipper',
      services: [
        chosen({
          origin: 'existing',
          base_url: 'http://nas:8096',
          state: 'failed',
          reason: 'auth_required',
        }),
      ],
    })
    const fetchStub = stubApi({
      [STATUS]: { body: revoked },
      'POST /api/setup/jellyfin/connect': { body: jellyfinSetup() },
      [RETEST]: {
        body: setupStatus({
          current_step: 2,
          owner: 'skipper',
          services: [chosen({ origin: 'existing', reason: 'setup_completed' })],
        }),
      },
    })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await screen.findByRole('heading', { level: 2, name: '先選 qBittorrent 是哪一台' })
    await user.click(within(screen.getByText('BTH 1').closest('li')!).getByRole('button'))

    expect(await screen.findByText('Berth 的 API key 要換一把')).toBeVisible()
    await user.type(screen.getByLabelText('Jellyfin 管理員帳號'), 'skipper')
    await user.type(screen.getByLabelText('Jellyfin 管理員密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: /登入/ }))

    await waitFor(() =>
      expect(requestsOf(fetchStub)).toEqual(
        expect.arrayContaining(['POST /api/setup/jellyfin/connect', RETEST]),
      ),
    )
    expect(bodiesOf(fetchStub, '/api/setup/services/jellyfin/test')).toEqual([{ restart: true }])
  })
})

describe('語言', () => {
  it('ZH / EN 切換整頁文案', async () => {
    stubApi({ [STATUS]: { body: setupStatus({ services: [ALL_BUNDLED[0]] }) } })
    const user = userEvent.setup()

    renderWithProviders(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: 'EN' }))

    expect(await screen.findByText('Create the Jellyfin administrator')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })
})

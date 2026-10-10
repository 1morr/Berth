import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import type { ChoiceRefusal } from '../api/setup'
import { stubApi } from '../test/fetch'
import { boardCells, findBoardCells } from '../test/board'
import { renderInRoute } from '../test/render'
import { ALL_BUNDLED, chosen, qbittorrentSetup, setupStatus } from '../test/fixtures'
import { useChoiceDraft } from '../setup/choiceDraft'
import { ServiceChoice } from '../setup/ServiceChoice'
import { SetupPage } from './SetupPage'

/**
 * 精靈的錯誤分層（M4 票 21）：一句人話在上、原文收進技術細節；換來源、換位址、重新測試、改欄位時
 * 上一次的結果不留在畫面上；既有與套件內各說各的。
 */

const STATUS = 'GET /api/setup/status'
const OWNER = 'POST /api/setup/owner'
const CHOOSE_JELLYFIN = 'POST /api/setup/services/jellyfin'
const RETEST_JELLYFIN = 'POST /api/setup/services/jellyfin/test'

afterEach(() => {
  vi.unstubAllGlobals()
})

const existingCard = () => screen.getByRole('radio', { name: /^既有/ })

/** 擁有者成立了，精靈在頁 2，qBittorrent 是既有的那一台而且沒通過。 */
function atExistingQbittorrent(overrides: Parameters<typeof chosen>[0]) {
  return setupStatus({
    current_step: 2,
    owner: 'skipper',
    services: [
      ALL_BUNDLED[0]!,
      chosen({
        kind: 'qbittorrent',
        origin: 'existing',
        base_url: 'http://nas:8080',
        state: 'failed',
        detail: '',
        ...overrides,
      }),
    ],
  })
}

describe('舊結果不留在畫面上', () => {
  it('換了位址：上一台 Jellyfin 那一段的失敗不再掛在擁有者表單上', async () => {
    const found = setupStatus({ services: [chosen()] })
    const elsewhere = setupStatus({
      services: [chosen({ origin: 'existing', base_url: 'http://nas:8096', detail: '12.1.0' })],
    })
    stubApi({
      [STATUS]: { body: found },
      [OWNER]: {
        status: 502,
        body: {
          detail: { reason: 'jellyfin_failed', detail: 'Jellyfin 10.10.7 is older than 12.0' },
        },
      },
      [CHOOSE_JELLYFIN]: { body: elsewhere },
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)

    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.type(screen.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))
    expect(await screen.findByText(/^Jellyfin 那一段沒做完/)).toBeVisible()

    await user.click(existingCard())
    await user.type(await screen.findByLabelText('位址'), 'http://nas:8096')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    // 表單回來了，說的是新的那一台：上一台的失敗不在。
    expect(await screen.findByRole('button', { name: '建立管理員並登入' })).toBeVisible()
    expect(screen.queryByText(/^Jellyfin 那一段沒做完/)).not.toBeInTheDocument()
    expect(screen.queryByText(/10\.10\.7/)).not.toBeInTheDocument()
  })

  it('重新測試：測試中不畫上一次的結果與補法', async () => {
    let answer: (value: { body: unknown }) => void = () => undefined
    stubApi({
      [STATUS]: {
        body: setupStatus({
          services: [chosen({ state: 'failed', reason: 'unreachable', detail: '' })],
        }),
      },
      [RETEST_JELLYFIN]: () => new Promise((resolve) => (answer = resolve)),
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/^容器還沒起來/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: '重新測試' }))

    await waitFor(() => expect(screen.queryByText(/^容器還沒起來/)).not.toBeInTheDocument())
    expect(screen.queryByText('找得到這台主機，但它沒有回應')).not.toBeInTheDocument()
    answer({ body: setupStatus({ services: [chosen()] }) })
    expect(await screen.findByText('連上了')).toBeInTheDocument()
  })

  it('換來源還沒測：泊位板那一格不再寫著原本那一台的「失敗 · 套件內」', async () => {
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
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)
    const board = await findBoardCells()
    const slot = () => within(board).getByText('BTH 2').closest('li')!
    await waitFor(() => expect(slot()).toHaveTextContent('套件內'))

    await user.click(existingCard())

    expect(slot()).toHaveTextContent('既有')
    expect(slot()).not.toHaveTextContent('套件內')
    expect(slot()).not.toHaveTextContent('失敗')
  })

  it('改了表單的一格：上一次的拒絕說的是舊值，收起來', async () => {
    const refusal: ChoiceRefusal = { reason: 'other_server', detail: 'bad-jellyfin' }
    function Page() {
      const draft = useChoiceDraft()
      return (
        <ServiceChoice
          kind="jellyfin"
          status={setupStatus({
            services: [
              chosen({
                origin: 'existing',
                base_url: 'http://nas:8096',
                state: 'failed',
                reason: 'other_server',
              }),
            ],
          })}
          sending={null}
          retesting={false}
          refusal={refusal}
          requestError={null}
          onChoose={vi.fn()}
          onRetest={vi.fn()}
          {...draft}
        />
      )
    }
    const user = userEvent.setup()
    render(<Page />)

    expect(screen.getByText(/這個位址上回答的是另一台 Jellyfin/)).toBeVisible()
    await user.type(screen.getByLabelText('位址'), '/')

    expect(screen.queryByText(/這個位址上回答的是另一台 Jellyfin/)).not.toBeInTheDocument()
  })
})

describe('既有與套件內各說各的', () => {
  it('既有 qBittorrent 帳密不對：標題與說明是既有那一套，補法不給 compose 指令', async () => {
    stubApi({ [STATUS]: { body: atExistingQbittorrent({ reason: 'auth_required' }) } })
    renderInRoute(<SetupPage />)

    expect(
      await screen.findByRole('heading', { name: '確認你的 qBittorrent', level: 2 }),
    ).toBeVisible()
    expect(screen.getByText(/這台 qBittorrent 是你自己的/)).toBeVisible()
    expect(screen.queryByText(/套件內的，Berth 直接改它的偏好/)).not.toBeInTheDocument()
    expect(screen.getByText('帳密不被接受')).toBeVisible()
    expect(screen.getByText(/^帳號或密碼不對/)).toBeVisible()
    // 補法不給 compose 指令；唯一的一行是「選了既有」那一段停掉套件內那一台的（M4 票 36）。
    expect(screen.getAllByText(/^docker compose/).map((line) => line.textContent)).toEqual([
      'docker compose stop qbittorrent',
    ])
  })

  it('既有 qBittorrent 太舊：連線那一條是紅的，說「至少要 4.4」，不叫人 docker compose pull', async () => {
    stubApi({
      [STATUS]: {
        body: atExistingQbittorrent({ reason: 'version_unsupported', detail: 'v4.3.9' }),
      },
    })
    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/至少要 qBittorrent 4\.4，這一台是 v4\.3\.9/)).toBeVisible()
    expect(screen.queryByText('連上了')).not.toBeInTheDocument()
    expect(screen.queryByText(/docker compose pull/)).not.toBeInTheDocument()
    const board = boardCells()
    expect(within(board).getByText('BTH 2').closest('li')).toHaveTextContent('失敗')
  })
})

describe('qBittorrent 的連錯與封鎖', () => {
  it('第 3 次起在密碼欄下預警還剩幾次', async () => {
    stubApi({
      [STATUS]: { body: atExistingQbittorrent({ reason: 'auth_required', auth_failures: 3 }) },
    })
    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/數到連續 3 次登入失敗.*最多再錯 2 次就會被封/)).toBeVisible()
  })

  it('數到上限之後不說「再錯 0 次」，說它多半已經封了', async () => {
    stubApi({
      [STATUS]: { body: atExistingQbittorrent({ reason: 'auth_required', auth_failures: 5 }) },
    })
    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/數到連續 5 次登入失敗.*已經封鎖/)).toBeVisible()
    expect(screen.queryByText(/再錯 \d 次/)).not.toBeInTheDocument()
  })

  it('連錯 2 次還不預警', async () => {
    stubApi({
      [STATUS]: { body: atExistingQbittorrent({ reason: 'auth_required', auth_failures: 2 }) },
    })
    renderInRoute(<SetupPage />)

    expect(await screen.findByText(/^帳號或密碼不對/)).toBeVisible()
    expect(screen.queryByText(/再錯 \d 次就會被封/)).not.toBeInTheDocument()
  })

  it('被封了：說等 60 分鐘或重啟 qBittorrent，不說「到它自己的介面解除」', async () => {
    stubApi({
      [STATUS]: { body: atExistingQbittorrent({ reason: 'ip_banned', auth_failures: 5 }) },
    })
    renderInRoute(<SetupPage />)

    const fix = await screen.findByText(/連錯 5 次就封鎖這個 IP 60 分鐘/)
    expect(fix).toHaveTextContent('重啟 qBittorrent')
    expect(screen.queryByText(/自己的介面解除/)).not.toBeInTheDocument()
  })
})

describe('頁 2 的連線卡跟著最新的失敗（M4 票 25，實測 B9-04～07）', () => {
  it('qBittorrent 停了：讀差異連不上就重新測試一次，卡片變紅、有「重新測試」，原因照實際例外', async () => {
    const qbittorrent = chosen({
      kind: 'qbittorrent',
      reason: 'connected',
      detail: 'v5.2.3 · Web API 2.15.1',
      base_url: 'http://qbittorrent:8080',
    })
    const stopped = setupStatus({
      current_step: 2,
      owner: 'skipper',
      services: [
        ALL_BUNDLED[0]!,
        { ...qbittorrent, state: 'failed', reason: 'not_deployed', detail: '' },
      ],
    })
    const fetch = stubApi({
      [STATUS]: {
        body: setupStatus({
          current_step: 3,
          owner: 'skipper',
          services: [ALL_BUNDLED[0]!, qbittorrent],
        }),
      },
      'GET /api/setup/qbittorrent/diff': {
        body: qbittorrentSetup({
          blocked: true,
          reachable: false,
          version: '',
          failure: 'not_deployed',
          error: 'GET /api/v2/app/version: host does not resolve',
        }),
      },
      'POST /api/setup/services/qbittorrent/test': { body: stopped },
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: '上一個泊位' }))

    expect(await screen.findByRole('button', { name: '重新測試' })).toBeVisible()
    expect(screen.getByText('沒通過')).toBeVisible()
    expect(screen.queryByText('連上了')).not.toBeInTheDocument()
    expect(screen.getByText(/容器沒在跑/)).toBeVisible()
    // 後端的頁 2 不再算做完：沒有前往下一個泊位。
    expect(screen.queryByRole('button', { name: '前往下一個泊位' })).not.toBeInTheDocument()
    const retests = fetch.mock.calls.filter(
      ([url, init]) => url === '/api/setup/services/qbittorrent/test' && init?.method === 'POST',
    )
    expect(retests).toHaveLength(1)
  })
})

describe('擁有者成立前目標被換（M4 票 28，實測 E12）', () => {
  const tested = chosen({
    origin: 'existing',
    base_url: 'http://localhost:58097',
    reason: 'setup_completed',
  })
  const swapped = chosen({
    origin: 'existing',
    base_url: 'http://localhost:48096',
    reason: 'setup_completed',
    server_id: '548d38d28268441f8d4bd0b0b7a6c1e2',
  })

  async function signIn(user: ReturnType<typeof userEvent.setup>) {
    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '登入' }))
  }

  it('送出時帶著畫面上測過的位址與 ServerId', async () => {
    const api = stubApi({
      [STATUS]: { body: setupStatus({ owner_signs_in: true, services: [tested] }) },
      [OWNER]: { body: setupStatus({ owner: 'skipper', current_step: 2, services: [tested] }) },
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)

    await signIn(user)

    await waitFor(() =>
      expect(api.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true),
    )
    const [, init] = api.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(init?.body))).toMatchObject({
      base_url: 'http://localhost:58097',
      server_id: tested.server_id,
      username: 'skipper',
    })
  })

  it('409 target_changed：說帳密沒送出、叫人重新測試；測完畫面換成新的那一台，打好的帳密不留', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ owner_signs_in: true, services: [tested] }) },
      [OWNER]: { status: 409, body: { detail: { reason: 'target_changed', detail: '' } } },
      [RETEST_JELLYFIN]: { body: setupStatus({ owner_signs_in: true, services: [swapped] }) },
    })
    const user = userEvent.setup()
    renderInRoute(<SetupPage />)

    await signIn(user)

    const said = await screen.findByText(/^Jellyfin 的位址在你填表時被換過/)
    expect(said).toHaveTextContent('帳密沒有送出去')
    const form = said.closest('form')!
    await user.click(within(form).getByRole('button', { name: '重新測試' }))

    expect(await screen.findAllByText('http://localhost:48096')).not.toHaveLength(0)
    expect(screen.queryByText(/^Jellyfin 的位址在你填表時被換過/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Jellyfin 帳號')).toHaveValue('')
    expect(screen.getByLabelText('密碼')).toHaveValue('')
  })
})

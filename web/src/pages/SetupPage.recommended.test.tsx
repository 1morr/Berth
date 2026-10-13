import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi, type StubRoute } from '../test/fetch'
import { renderInRoute } from '../test/render'
import {
  ALL_BUNDLED,
  OTHER_PUBLIC,
  RECOMMENDED,
  check,
  chosen,
  indexerSetup,
  setupStatus,
  site,
  step,
} from '../test/fixtures'
import { SetupPage } from './SetupPage'

/**
 * 頁 4 套件內一鍵加入可用的推薦站（M4 票 44，審計 E-5）。
 *
 * 一顆主鍵完成測試與加入；逐站的清單與其他公開站收進「進階」、照樣能用。Prowlarr 已經有站時不給主鍵。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const INDEXERS = 'GET /api/setup/indexers'
const RUN = 'POST /api/setup/indexers/recommended'
const TEST_SITES = 'POST /api/setup/indexers/test'
const ADD_INDEXERS = 'POST /api/setup/indexers/apply'
const RETEST = 'POST /api/setup/services/prowlarr/test'

const AT_INDEXER = setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED })
const CLOUDFLARE = 'Unable to access 1337x.to, blocked by CloudFlare Protection.'
const UNREACHABLE = 'Unable to connect to indexer, check the log above the ValidationFailure.'
const RUN_LABEL = '測試推薦站，加入通過的'
const ADVANCED = '進階：逐站測試與挑選、其他公開站'

/** 主鍵跑完：六站加進去、ACG.RIP 測過而加不進去、1337x 與 EZTV 測試就沒過。 */
const ADDED_NAMES = ['nyaasi', 'dmhy', 'animetosho-xyz', 'mikan', 'yts', 'thepiratebay']
const AFTER_RUN = indexerSetup({
  web_ui_username: 'skipper',
  sites: RECOMMENDED.filter((row) => ADDED_NAMES.includes(row.definition_name)).map((row, index) =>
    site(row, index + 1),
  ),
  steps: [
    ...ADDED_NAMES.map((name) => step(name, 'ok')),
    step('acgrip', 'failed', '', UNREACHABLE),
    step('1337x', 'failed', '', CLOUDFLARE),
    step('eztv', 'failed', '', CLOUDFLARE),
    step('prowlarr_login', 'skipped', 'skipper'),
  ],
  checks: [
    ...ADDED_NAMES.map((name) => check(name)),
    check('acgrip', 'unreachable', UNREACHABLE, 'add'),
    check('1337x', 'cloudflare', CLOUDFLARE, 'test'),
    check('eztv', 'cloudflare', CLOUDFLARE, 'test'),
  ],
})

function called(stub: ReturnType<typeof stubApi>, url: string) {
  return stub.mock.calls.some(([target]) => target === url)
}

describe('頁 4 套件內的主鍵', () => {
  it('一顆鍵完成測試與加入：只送一支，結果逐站列出，測過而加不進去的另外說', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup({ web_ui_username: 'skipper' }) },
      [RUN]: { body: AFTER_RUN },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const block = within(await screen.findByTestId('recommended-sites'))
    expect(block.getByText(/測試推薦的 9 個公開站/)).toBeVisible()
    await user.click(block.getByRole('button', { name: RUN_LABEL }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/recommended')).toBe(true))
    // 不經逐站的測試與加入：一支做完。
    expect(called(fetchStub, '/api/setup/indexers/test')).toBe(false)
    expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(false)

    const outcome = within(await screen.findByTestId('one-key-outcome'))
    expect(outcome.getByText('加入 6 站 · 1 站測過、加不進去 · 2 站沒通過測試')).toHaveAttribute(
      'aria-live',
      'polite',
    )
    const addFailed = within(outcome.getByTestId('add-failed'))
    expect(addFailed.getByText('ACG.RIP')).toBeVisible()
    expect(addFailed.getByText(/Prowlarr 加入前自己再連一次卻沒連上/)).toBeVisible()
    expect(addFailed.getByText(/連不上：DNS、TLS/)).toBeVisible()
    const testFailed = within(outcome.getByTestId('test-failed'))
    expect(testFailed.getByText('1337x')).toBeVisible()
    expect(testFailed.getByText('EZTV')).toBeVisible()
    expect(testFailed.queryByText('ACG.RIP')).not.toBeInTheDocument()
    // 加不進去的不算進已加入。
    const added = within(screen.getByTestId('added'))
    expect(added.getByText('6 站')).toBeInTheDocument()
    expect(added.queryByText('ACG.RIP')).not.toBeInTheDocument()
    // 站已經有了：主鍵不再出現，前進靠底部導覽。
    expect(screen.queryByRole('button', { name: RUN_LABEL })).not.toBeInTheDocument()
  })

  it('跑完之後「進階」那一份清單看得到同樣的結論', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup({ web_ui_username: 'skipper' }) },
      [RUN]: { body: AFTER_RUN },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: RUN_LABEL }))
    await screen.findByTestId('one-key-outcome')
    await user.click(screen.getByText(ADVANCED))

    const add = within(screen.getByRole('region', { name: '加站' }))
    expect(add.getByRole('checkbox', { name: '1337x' })).toBeDisabled()
    expect(add.getAllByText(/被 Cloudflare 擋住/)).toHaveLength(2)
    expect(add.getByTestId('check-summary')).toHaveTextContent('3 站沒通過')
  })

  it('Prowlarr 已經有站（重跑、重裝）：沒有主鍵，進階清單照樣測、勾、加', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: {
        body: indexerSetup({ web_ui_username: 'skipper', sites: [site(RECOMMENDED[1], 1)] }),
      },
      [TEST_SITES]: { body: { checks: [check('yts', null, '', 'test')] } },
      [ADD_INDEXERS]: {
        body: indexerSetup({
          web_ui_username: 'skipper',
          sites: [site(RECOMMENDED[1], 1), site(RECOMMENDED[6], 2)],
          steps: [step('yts', 'ok')],
          checks: [check('yts')],
        }),
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await screen.findByTestId('added')
    expect(screen.queryByRole('button', { name: RUN_LABEL })).not.toBeInTheDocument()
    // 「進階」預設收起：裡面的東西看不到。
    expect(screen.getByRole('button', { name: '測試全部' })).not.toBeVisible()

    await user.click(screen.getByText(ADVANCED))
    expect(screen.getByRole('button', { name: '測試全部' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: '測試 YTS' }))
    const yts = screen.getByRole('checkbox', { name: 'YTS' })
    await waitFor(() => expect(yts).toBeEnabled())
    await user.click(yts)
    await user.click(screen.getByRole('button', { name: '加入 1 個站' }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(true))
    expect(called(fetchStub, '/api/setup/indexers/recommended')).toBe(false)
    expect(await within(screen.getByTestId('added')).findByText('2 站')).toBeInTheDocument()
  })

  it('主鍵跑著的時候不送介面登入：設完 Prowlarr 會重啟，正在加的站撞上它', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup() },
      [RUN]: () => new Promise<StubRoute>(() => undefined),
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const login = within(await screen.findByTestId('prowlarr-login'))
    expect(login.getByRole('button', { name: '設定介面登入' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: RUN_LABEL }))

    expect(await screen.findByRole('button', { name: '測試並加入中…' })).toBeInTheDocument()
    expect(login.getByRole('button', { name: '設定介面登入' })).toBeDisabled()
  })

  it('請求沒走完：說出來，主鍵還按得下去', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: indexerSetup({ web_ui_username: 'skipper' }) },
      [RUN]: () => Promise.reject(new TypeError('Failed to fetch')),
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    await user.click(await screen.findByRole('button', { name: RUN_LABEL }))

    const block = within(screen.getByTestId('recommended-sites'))
    expect(await block.findByTestId('request-failed')).toHaveTextContent(/測試與加入沒做完/)
    expect(block.getByRole('button', { name: RUN_LABEL })).toBeEnabled()
  })
})

/** 既有 Prowlarr、一站都沒有：連得上、0 站。 */
const EXISTING_PROWLARR = chosen({
  kind: 'prowlarr',
  origin: 'existing',
  base_url: 'http://nas:9696',
  reason: 'connected',
  detail: '0',
})
const AT_EXISTING = setupStatus({
  ...AT_INDEXER,
  services: [...ALL_BUNDLED.slice(0, 2), EXISTING_PROWLARR],
})
const EXISTING_EMPTY = indexerSetup({
  origin: 'existing',
  base_url: 'http://nas:9696',
  web_ui_login: false,
  web_port: null,
  steps: [step('prowlarr', 'pending', '0')],
})

describe('頁 4 既有 Prowlarr 也有主鍵（M4 票 67，審計 C3、P2-10）', () => {
  it('一站都沒有：同一顆鍵，說出會測哪幾站、加進哪一台；一支做完，沒有介面登入', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_EXISTING },
      [INDEXERS]: { body: EXISTING_EMPTY },
      [RUN]: {
        body: indexerSetup({
          ...EXISTING_EMPTY,
          sites: RECOMMENDED.filter((row) => ADDED_NAMES.includes(row.definition_name)).map(
            (row, index) => site(row, index + 1),
          ),
          steps: [step('prowlarr', 'ok', '6'), ...ADDED_NAMES.map((name) => step(name, 'ok'))],
          checks: ADDED_NAMES.map((name) => check(name)),
        }),
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const block = within(await screen.findByTestId('recommended-sites'))
    const lede = block.getByText(/加進你在 nas:9696 的 Prowlarr/)
    expect(lede).toHaveTextContent('測試推薦的 9 個公開站（Nyaa.si、')
    expect(lede).toHaveTextContent('Berth 不移除站')
    expect(screen.queryByTestId('prowlarr-login')).not.toBeInTheDocument()
    await user.click(block.getByRole('button', { name: RUN_LABEL }))

    await waitFor(() => expect(called(fetchStub, '/api/setup/indexers/recommended')).toBe(true))
    expect(called(fetchStub, '/api/setup/indexers/test')).toBe(false)
    expect(called(fetchStub, '/api/setup/indexers/apply')).toBe(false)
    const outcome = within(await screen.findByTestId('one-key-outcome'))
    expect(outcome.getByText('加入 6 站')).toBeVisible()
  })

  it('已經有站：沒有主鍵，逐站加站收在「進階」', async () => {
    stubApi({
      [STATUS]: { body: AT_EXISTING },
      [INDEXERS]: {
        body: indexerSetup({ ...EXISTING_EMPTY, sites: [site(RECOMMENDED[1], 1)] }),
      },
    })

    renderInRoute(<SetupPage />)

    expect(await screen.findByTestId('added')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: RUN_LABEL })).not.toBeInTheDocument()
    const advanced = screen.getByTestId('advanced-sites')
    expect(advanced).not.toHaveAttribute('open')
    expect(within(advanced).getByRole('region', { name: '加站' })).toBeInTheDocument()
  })

  it('In English the one key names the sites and your Prowlarr', async () => {
    await i18next.changeLanguage('en')
    try {
      stubApi({ [STATUS]: { body: AT_EXISTING }, [INDEXERS]: { body: EXISTING_EMPTY } })

      renderInRoute(<SetupPage />)
      const block = within(await screen.findByTestId('recommended-sites'))

      expect(
        block.getByText(/adds the ones that pass to your Prowlarr at nas:9696/),
      ).toHaveTextContent('Berth does not remove sites')
      expect(
        block.getByRole('button', { name: 'Test recommended sites and add the ones that pass' }),
      ).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

/**
 * Prowlarr 裡沒有推薦站的定義（M4 票 73，實跑 L4）：它連不上 `indexers.prowlarr.com` 時只剩磁碟上的幾個，
 * 主鍵沒有東西可測。原本整段只剩標題與「之後再說」，主鍵無聲無息地不見。
 */
describe('頁 4 推薦站不在 Prowlarr 裡', () => {
  const ALL_GONE = indexerSetup({
    web_ui_username: 'skipper',
    candidates: OTHER_PUBLIC,
    unlisted: RECOMMENDED.map((row) => row.definition_name),
  })

  it('一個都不在：說出原因與下一步，「重新讀取」重問 Prowlarr，「之後再說」與「進階」都還在', async () => {
    const fetchStub = stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: ALL_GONE },
      [RETEST]: { body: AT_INDEXER },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const block = within(await screen.findByTestId('recommended-sites'))
    const notice = within(block.getByTestId('unlisted'))
    expect(notice.getByText(/Prowlarr 還沒拿到站的清單/)).toBeVisible()
    expect(notice.getByText(/indexers\.prowlarr\.com/)).toBeVisible()
    expect(notice.getByRole('link', { name: '開啟 Prowlarr 的 Events' })).toHaveAttribute(
      'href',
      expect.stringMatching(/:9696\/system\/events$/),
    )
    expect(block.queryByRole('button', { name: RUN_LABEL })).not.toBeInTheDocument()
    expect(block.getByRole('button', { name: '之後再說' })).toBeEnabled()
    expect(screen.getByText(ADVANCED)).toBeVisible()

    await user.click(notice.getByRole('button', { name: '重新讀取' }))
    await waitFor(() => expect(called(fetchStub, '/api/setup/services/prowlarr/test')).toBe(true))
  })

  it('只有一部分在：主鍵照舊，跑完之後列出 Prowlarr 裡沒有的那幾站', async () => {
    const gone = ['mikan', 'yts']
    const present = RECOMMENDED.filter((row) => !gone.includes(row.definition_name))
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: {
        body: indexerSetup({
          web_ui_username: 'skipper',
          candidates: [...present, ...OTHER_PUBLIC],
          unlisted: gone,
        }),
      },
      [RUN]: {
        body: indexerSetup({
          web_ui_username: 'skipper',
          sites: [site(present[0], 1)],
          candidates: [...present.slice(1), ...OTHER_PUBLIC],
          unlisted: gone,
          steps: [step('nyaasi', 'ok')],
          checks: [check('nyaasi')],
        }),
      },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const block = within(await screen.findByTestId('recommended-sites'))
    expect(block.queryByTestId('unlisted')).not.toBeInTheDocument()
    expect(block.getByText(/測試推薦的 7 個公開站/)).toBeVisible()
    await user.click(block.getByRole('button', { name: RUN_LABEL }))

    const outcome = within(await screen.findByTestId('one-key-outcome'))
    expect(outcome.getByTestId('unlisted-sites')).toHaveTextContent(
      'Prowlarr 裡沒有 2 個推薦站，沒有測：mikan、yts',
    )
  })

  it('英文也說得出來', async () => {
    stubApi({
      [STATUS]: { body: AT_INDEXER },
      [INDEXERS]: { body: ALL_GONE },
    })

    await i18next.changeLanguage('en')
    try {
      renderInRoute(<SetupPage />)
      const notice = within(await screen.findByTestId('unlisted'))
      expect(notice.getByText(/Prowlarr has not got its list of sites yet/)).toBeVisible()
      expect(notice.getByRole('button', { name: 'Re-read' })).toBeEnabled()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('既有 Prowlarr 一站都沒有、推薦站也一個都不在：一段說完，不另外畫「沒有站」', async () => {
    // 兩張票疊在一起（M4 票 67 讓既有的那一台也走主鍵）：「沒有站」叫人在下面測推薦站，這時那裡沒有推薦站。
    const fetchStub = stubApi({
      [STATUS]: { body: AT_EXISTING },
      [INDEXERS]: {
        body: indexerSetup({
          ...EXISTING_EMPTY,
          candidates: OTHER_PUBLIC,
          unlisted: RECOMMENDED.map((row) => row.definition_name),
        }),
      },
      [RETEST]: { body: AT_EXISTING },
    })
    const user = userEvent.setup()

    renderInRoute(<SetupPage />)
    const notice = within(await screen.findByTestId('unlisted'))
    expect(notice.getByText(/這一台 Prowlarr 還沒有任何站，Berth 什麼都搜不到/)).toBeVisible()
    expect(notice.getByText(/推薦的站一個都不在/)).toBeVisible()
    expect(notice.getByText(/到 Prowlarr 自己加站後按「重新讀取」/)).toBeVisible()
    expect(notice.getByRole('link', { name: '開啟 Prowlarr 的 Events' })).toHaveAttribute(
      'href',
      'http://nas:9696/system/events',
    )
    expect(screen.queryByTestId('no-sites')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '重新讀取' })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: RUN_LABEL })).not.toBeInTheDocument()
    expect(screen.getByText(ADVANCED)).toBeVisible()

    await user.click(notice.getByRole('button', { name: '重新讀取' }))
    await waitFor(() => expect(called(fetchStub, '/api/setup/services/prowlarr/test')).toBe(true))
  })

  it('既有 Prowlarr 一站都沒有、推薦站都在：照舊是「沒有站」加主鍵', async () => {
    stubApi({ [STATUS]: { body: AT_EXISTING }, [INDEXERS]: { body: EXISTING_EMPTY } })

    renderInRoute(<SetupPage />)

    expect(await screen.findByTestId('no-sites')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: RUN_LABEL })).toBeVisible()
    expect(screen.queryByTestId('unlisted')).not.toBeInTheDocument()
  })
})

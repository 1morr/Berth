import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi, type StubRoute } from '../test/fetch'
import { renderInRoute } from '../test/render'
import {
  ALL_BUNDLED,
  RECOMMENDED,
  SEQUENCE_DONE,
  chosen,
  indexerSetup,
  jellyfinSetup,
  qbittorrentSetup,
  routeSetup,
  setupStatus,
  site,
  step,
  tmdbSetup,
} from '../test/fixtures'
import { SetupPage } from './SetupPage'

/**
 * M4 票 68：精靈各頁之間的說法與狀態一致（`docs/research/usability-audit-2026-10-07.md` §8 P2）。每一點照
 * zh-Hant 與 en 各跑一次：文案改的是成對的 key，兩種語言都要說得出同一件事。
 */

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18next.changeLanguage('zh-Hant')
})

const LANGUAGES = ['zh-Hant', 'en'] as const

const STATUS = 'GET /api/setup/status'
const SIGN_IN_BUNDLED = 'POST /api/setup/owner'
const CHOOSE_QBITTORRENT = 'POST /api/setup/services/qbittorrent'
const CHOOSE_PROWLARR = 'POST /api/setup/services/prowlarr'
const QBITTORRENT = 'GET /api/setup/qbittorrent/diff'
const INDEXERS = 'GET /api/setup/indexers'
const JELLYFIN = 'GET /api/setup/jellyfin'
const ROUTES = 'GET /api/setup/routes'
const REREAD = 'POST /api/setup/routes/libraries'
const TMDB = 'GET /api/setup/tmdb'
const COMPOSE = 'GET /api/setup/compose'
const SET_LOGIN = 'PUT /api/setup/indexers/login'

// 測試照語言逐 key 取文案，key 有一部分是組出來的（`owner.refused.${reason}`）：過不了 `strictKeyChecks`，
// 在這裡收成字串。
const t = (key: string, options?: Record<string, unknown>): string =>
  String(i18next.t(key as never, options))

/** 右欄剖面（`Cutaway` 是一個以標題命名的 section）。 */
async function cutaway(title: string) {
  const heading = await screen.findByRole('heading', { level: 3, name: title })
  return within(heading.closest('section')!)
}

const EXISTING_JELLYFIN = chosen({
  origin: 'existing',
  base_url: 'http://nas:8096',
  reason: 'setup_completed',
  detail: '12.0.0',
})

describe.each(LANGUAGES)('%s', (language) => {
  async function speak() {
    await i18next.changeLanguage(language)
  }

  describe('頁 1', () => {
    /** 重裝保留了 Jellyfin 的設定：套件內那一台已經有管理員，這一頁是登入。 */
    const SIGNING_IN = setupStatus({ services: [chosen()], owner_signs_in: true })

    it('右欄只列會動的：現在建 API key、媒體庫到頁 3 才動，不再說「不改任何設定」（審計 P2-16）', async () => {
      await speak()
      stubApi({ [STATUS]: { body: SIGNING_IN } })

      renderInRoute(<SetupPage />)

      const plan = await cutaway(t('owner.cutaway.title'))
      expect(plan.getByText(t('owner.cutaway.apiKey'))).toBeInTheDocument()
      expect(plan.getByText(t('owner.cutaway.later')).nextElementSibling).toHaveTextContent(
        language === 'en' ? /^Libraries: only when .* page 3$/ : /^媒體庫：到頁 3 .*才動$/,
      )
      expect(
        plan.queryByText(language === 'en' ? /Nothing on this Jellyfin/ : /任何設定/),
      ).not.toBeInTheDocument()
    })

    it.each([
      ['invalid_credentials', 401],
      ['not_administrator', 403],
    ] as const)('套件內那一台登入被拒（%s）：標在帳密兩格上（審計 P2-5）', async (reason, code) => {
      await speak()
      stubApi({
        [STATUS]: { body: SIGNING_IN },
        [SIGN_IN_BUNDLED]: { status: code, body: { detail: { reason, detail: '' } } },
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.type(await screen.findByLabelText(t('owner.field.username')), 'skipper')
      await user.type(screen.getByLabelText(t('owner.field.password')), 'harbour')
      await user.click(screen.getByRole('button', { name: t('owner.submit.signIn') }))

      const said = t(`owner.refused.${reason}`)
      expect(await screen.findByRole('alert')).toHaveTextContent(said)
      for (const label of ['owner.field.username', 'owner.field.password']) {
        const field = screen.getByLabelText(t(label))
        expect(field).toHaveAttribute('aria-invalid', 'true')
        expect(field).toHaveAccessibleDescription(said)
      }
      // 只說一次：表單層級的那一塊不再重複。
      expect(screen.getAllByText(said)).toHaveLength(1)
    })

    it('既有那一台登入不是管理員：標在帳密兩格上（審計 P2-5）', async () => {
      await speak()
      stubApi({
        [STATUS]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
        'POST /api/setup/owner/existing': {
          status: 403,
          body: { detail: { reason: 'not_administrator', detail: '' } },
        },
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.type(await screen.findByLabelText(t('owner.field.username')), 'deckhand')
      await user.type(screen.getByLabelText(t('connect.field.password')), 'rope')
      await user.click(screen.getByRole('button', { name: t('connect.signIn') }))

      const said = t('owner.refused.not_administrator')
      expect(await screen.findByRole('alert')).toHaveTextContent(said)
      for (const label of ['owner.field.username', 'connect.field.password']) {
        expect(screen.getByLabelText(t(label))).toHaveAttribute('aria-invalid', 'true')
      }
      expect(screen.getAllByText(said)).toHaveLength(1)
    })

    it('密碼空著登入既有那一台：先說密碼沒填（審計 P2-20）', async () => {
      await speak()
      stubApi({
        [STATUS]: { body: setupStatus({ services: [EXISTING_JELLYFIN], owner_signs_in: true }) },
        'POST /api/setup/owner/existing': {
          status: 401,
          body: { detail: { reason: 'invalid_credentials', detail: '' } },
        },
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.type(await screen.findByLabelText(t('owner.field.username')), 'skipper')
      await user.click(screen.getByRole('button', { name: t('connect.signIn') }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        language === 'en' ? /^The password is empty\./ : /^密碼沒填。/,
      )
      // 錯的只有密碼那一格。
      expect(screen.getByLabelText(t('connect.field.password'))).toHaveAttribute(
        'aria-invalid',
        'true',
      )
      expect(screen.getByLabelText(t('owner.field.username'))).not.toHaveAttribute(
        'aria-invalid',
        'true',
      )
    })

    it('擁有者成立之後，選了既有的那一台照樣說要停掉套件內那一台（審計 P2-20）', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 2, owner: 'skipper', services: [EXISTING_JELLYFIN] }),
        },
      })

      renderInRoute(<SetupPage />, '/setup?step=1')

      expect(
        await screen.findByText(t('choice.existing.profiles', { kind: 'jellyfin' })),
      ).toBeVisible()
      expect(screen.getByText('COMPOSE_PROFILES=qbittorrent,prowlarr')).toBeInTheDocument()
      expect(screen.getByText('docker compose stop jellyfin')).toBeInTheDocument()
    })
  })

  describe('頁 2、頁 4：選了套件內、請求還在路上', () => {
    it('頁 2 的剖面與頁 4 一樣說接法（票 81 留下的）', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 2, owner: 'skipper', services: [ALL_BUNDLED[0]] }),
        },
        [CHOOSE_QBITTORRENT]: () => new Promise<StubRoute>(() => {}),
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.click(
        await screen.findByRole('radio', { name: new RegExp(`^${t('choice.bundled.title')}`) }),
      )

      const server = await cutaway(t('qbittorrent.cutaway.server'))
      expect(server.getByText(t('qbittorrent.cutaway.kind')).nextElementSibling).toHaveTextContent(
        t('qbittorrent.cutaway.bundled'),
      )
      // 還沒連上：版本照實說不知道。
      expect(server.getByText(t('detail.version')).nextElementSibling).toHaveTextContent('—')
      // 標題與 lede 也不再問「先選」。
      expect(
        screen.queryByRole('heading', { level: 2, name: t('qbittorrent.title.choose') }),
      ).not.toBeInTheDocument()
    })

    it('頁 4 還沒選來源時，右欄不寫接法（審計 P2-1）', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 4,
            owner: 'skipper',
            services: ALL_BUNDLED.slice(0, 2),
          }),
        },
        [INDEXERS]: { body: indexerSetup({ origin: null, base_url: '', api_key_present: false }) },
      })

      renderInRoute(<SetupPage />)

      const plans = await cutaway(t('owner.cutaway.title'))
      expect(plans.getByText(t('indexer.cutaway.bundledPlan'))).toBeInTheDocument()
      expect(screen.queryByText(t('indexer.cutaway.kind'))).not.toBeInTheDocument()
      expect(screen.queryByText(t('indexer.cutaway.existing'))).not.toBeInTheDocument()
    })

    it('頁 4 的 lede 不再說「先選 Prowlarr 是哪一台」（票 81 留下的）', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 4,
            owner: 'skipper',
            services: ALL_BUNDLED.slice(0, 2),
          }),
        },
        [INDEXERS]: { body: indexerSetup({ origin: null, base_url: '', api_key_present: false }) },
        [CHOOSE_PROWLARR]: () => new Promise<StubRoute>(() => {}),
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      expect(await screen.findByText(t('indexer.lede.choose'))).toBeVisible()
      await user.click(
        screen.getByRole('radio', { name: new RegExp(`^${t('choice.bundled.title')}`) }),
      )

      expect(await screen.findByText(t('indexer.lede.bundled'))).toBeVisible()
      expect(screen.queryByText(t('indexer.lede.choose'))).not.toBeInTheDocument()
    })
  })

  describe('介面登入的狀態詞（審計 P2-2）', () => {
    it('加站之後頁 4 的登入那一條重算成 skipped，照樣說「已完成」，與頁 2 同一個字', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 5, owner: 'skipper', services: ALL_BUNDLED }),
        },
        [INDEXERS]: {
          body: indexerSetup({
            sites: [site(RECOMMENDED[0], 1)],
            steps: [step('prowlarr_login', 'skipped', 'skipper')],
            web_ui_username: 'skipper',
            web_ui_login_by_berth: true,
          }),
        },
        [TMDB]: { body: tmdbSetup() },
      })

      renderInRoute(<SetupPage />, '/setup?step=4')

      const login = await screen.findByTestId('prowlarr-login')
      expect(within(login).getByText(t('status.ok'))).toBeInTheDocument()
      expect(within(login).queryByText(t('status.skipped'))).not.toBeInTheDocument()
      // 設好了就不再標必填，與頁 2 設好之後一樣。
      expect(within(login).queryByText(t('indexer.login.required'))).not.toBeInTheDocument()
    })

    it.each([
      [true, 'status.ok'],
      [false, 'status.skipped'],
    ] as const)(
      '頁 2 的登入那一條是 skipped：這個 Berth 設的（%s）說「已完成」，那一台原本就有的照舊',
      async (byBerth, said) => {
        await speak()
        stubApi({
          [STATUS]: {
            body: setupStatus({
              current_step: 3,
              owner: 'skipper',
              services: ALL_BUNDLED.slice(0, 2),
            }),
          },
          [QBITTORRENT]: {
            body: qbittorrentSetup({
              steps: [step('web_ui_password', 'skipped', 'keeper')],
              web_ui_username: 'keeper',
              web_ui_login_by_berth: byBerth,
            }),
          },
          [JELLYFIN]: { body: jellyfinSetup({ steps: SEQUENCE_DONE }) },
          [ROUTES]: { body: routeSetup() },
          [REREAD]: { body: routeSetup() },
        })

        renderInRoute(<SetupPage />, '/setup?step=2')

        // 原本就有的（重裝）不說「已完成」：完成頁說的是「這一輪精靈沒有設它」。
        const sequence = await screen.findByTestId('sequence')
        expect(await within(sequence).findByText(t(said))).toBeInTheDocument()
      },
    )

    it('介面登入正在送時，前進鍵的位置只說還差加站，不說還差介面登入', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED }),
        },
        [INDEXERS]: { body: indexerSetup({ steps: [step('prowlarr_login', 'pending')] }) },
        [SET_LOGIN]: () => new Promise<StubRoute>(() => {}),
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      const login = await screen.findByTestId('prowlarr-login')
      const nav = () => within(screen.getByRole('navigation', { name: t('setup.nav.label') }))
      expect(nav().getByRole('button', { name: t('indexer.gap.login') })).toBeInTheDocument()

      await user.type(within(login).getByLabelText(t('interfaceLogin.password')), 'harbour1')
      await user.type(within(login).getByLabelText(t('interfaceLogin.confirm')), 'harbour1')
      await user.click(within(login).getByRole('button', { name: t('indexer.login.save') }))

      await waitFor(() =>
        expect(
          nav().queryByRole('button', { name: t('indexer.gap.login') }),
        ).not.toBeInTheDocument(),
      )
      expect(nav().getByRole('button', { name: t('indexer.gap.sites') })).toBeInTheDocument()
    })
  })

  describe('頁 3：重裝時不自己開跑（審計 P2-11）', () => {
    const REINSTALLED = jellyfinSetup({
      // 這個 Berth 沒跑過建媒體庫那一步，那一台上卻已經建好了：上一次留下的。
      steps: SEQUENCE_DONE.filter((row) => row.step !== 'libraries'),
      api_key_present: true,
      bundled_default: true,
      bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
    })

    it('說為什麼、要按哪一顆，而且不送寫入', async () => {
      await speak()
      const fetch = stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 3,
            owner: 'skipper',
            services: ALL_BUNDLED.slice(0, 2),
          }),
        },
        [JELLYFIN]: { body: REINSTALLED },
        [ROUTES]: { body: routeSetup() },
        [REREAD]: { body: routeSetup() },
      })

      renderInRoute(<SetupPage />)

      expect(await screen.findByText(t('routes.heldBack'))).toBeVisible()
      expect(t('routes.heldBack')).toContain(t('routes.dock.build'))
      expect(screen.getByRole('button', { name: t('routes.dock.build') })).toBeEnabled()
      const written = fetch.mock.calls.filter(
        ([url, init]) =>
          (init?.method ?? 'GET') !== 'GET' && String(url) !== '/api/setup/routes/libraries',
      )
      expect(written).toEqual([])
    })

    it('這一輪自己建過（那一步跑過）時不說是重裝', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 3,
            owner: 'skipper',
            services: ALL_BUNDLED.slice(0, 2),
          }),
        },
        [JELLYFIN]: { body: { ...REINSTALLED, steps: SEQUENCE_DONE } },
        [ROUTES]: { body: routeSetup() },
        [REREAD]: { body: routeSetup() },
      })

      renderInRoute(<SetupPage />)

      await screen.findByRole('button', { name: t('routes.dock.build') })
      expect(screen.queryByText(t('routes.heldBack'))).not.toBeInTheDocument()
    })
  })

  describe('完成頁', () => {
    const AT_THE_END = setupStatus({ current_step: 6, owner: 'skipper', services: ALL_BUNDLED })
    const BUILT = routeSetup({ ready: true })

    function end(routes: Parameters<typeof stubApi>[0]) {
      return stubApi({
        [STATUS]: { body: AT_THE_END },
        [ROUTES]: { body: BUILT },
        [TMDB]: { body: tmdbSetup() },
        [INDEXERS]: { body: indexerSetup() },
        [QBITTORRENT]: { body: qbittorrentSetup() },
        ...routes,
      })
    }

    async function doors() {
      const heading = await screen.findByRole('heading', { name: t('complete.doors.title') })
      return within(heading.closest('section')!)
    }

    it('沿用頁 1 那一組時說「與 Jellyfin 同一組」（審計 P2-3）', async () => {
      await speak()
      const ours = { web_ui_username: 'skipper', web_ui_login_by_berth: true }
      end({
        [QBITTORRENT]: {
          body: qbittorrentSetup({ ...ours, web_ui_login_reuses_owner: true }),
        },
        [INDEXERS]: { body: indexerSetup({ ...ours, web_ui_login_reuses_owner: false }) },
      })

      renderInRoute(<SetupPage />)

      const listed = await doors()
      expect(
        await listed.findByText(t('complete.doors.ownerLogin', { name: 'skipper' })),
      ).toBeInTheDocument()
      // 自設的那一組照舊是「精靈裡設的」：沿用是逐台記的。
      expect(
        listed.getByText(t('complete.doors.bundledLogin', { name: 'skipper' })),
      ).toBeInTheDocument()
    })

    it('沿用上一位擁有者設的那一組時說忘了去哪裡換（審計 P2-21）', async () => {
      await speak()
      end({
        [QBITTORRENT]: { body: qbittorrentSetup({ web_ui_username: 'keeper' }) },
        [INDEXERS]: { body: indexerSetup({ web_ui_username: 'audit' }) },
      })

      renderInRoute(<SetupPage />)

      const listed = await doors()
      const where =
        language === 'en'
          ? /Settings → qBittorrent, Interface login/
          : /「設定 → qBittorrent」的「介面登入」/
      expect(await listed.findByText(where)).toHaveTextContent('keeper')
      expect(
        listed.getByText(language === 'en' ? /Settings → Prowlarr/ : /「設定 → Prowlarr」/),
      ).toHaveTextContent('audit')
    })

    it('選了既有的服務，套件內那一台還在跑就再提醒一次停掉（審計 P2-20）', async () => {
      await speak()
      end({
        [STATUS]: {
          body: setupStatus({
            ...AT_THE_END,
            services: [
              EXISTING_JELLYFIN,
              ...ALL_BUNDLED.slice(1, 2),
              { ...ALL_BUNDLED[2], origin: 'existing' },
            ],
          }),
        },
        // Prowlarr 的套件內那一台已經停了：不再叫人停它。
        [COMPOSE]: { body: { resolvable: { jellyfin: true, qbittorrent: true, prowlarr: false } } },
      })

      renderInRoute(<SetupPage />)

      const heading = await screen.findByRole('heading', { name: t('complete.idle.title') })
      const unused = within(heading.closest('section')!)
      expect(unused.getByText(t('complete.idle.body', { services: 'Jellyfin' }))).toBeVisible()
      expect(unused.getByText('COMPOSE_PROFILES=qbittorrent')).toBeInTheDocument()
      expect(unused.getByText('docker compose stop jellyfin')).toBeInTheDocument()
    })

    it('三個都選既有：COMPOSE_PROFILES 那一行是空的，說空著就是只跑 Berth', async () => {
      await speak()
      end({
        [STATUS]: {
          body: setupStatus({
            ...AT_THE_END,
            services: ALL_BUNDLED.map((row) => ({ ...row, origin: 'existing' as const })),
          }),
        },
        [COMPOSE]: { body: { resolvable: { jellyfin: true, qbittorrent: true, prowlarr: true } } },
      })

      renderInRoute(<SetupPage />)

      const heading = await screen.findByRole('heading', { name: t('complete.idle.title') })
      const unused = within(heading.closest('section')!)
      expect(unused.getByText('COMPOSE_PROFILES=')).toBeInTheDocument()
      expect(unused.getByText(new RegExp(t('complete.idle.onlyBerth')))).toBeVisible()
      expect(
        unused.getByText('docker compose stop jellyfin qbittorrent prowlarr'),
      ).toBeInTheDocument()
    })

    it('全部套件內時沒有這一段', async () => {
      await speak()
      end({})

      renderInRoute(<SetupPage />)

      await doors()
      await waitFor(() =>
        expect(
          screen.queryByRole('heading', { name: t('complete.idle.title') }),
        ).not.toBeInTheDocument(),
      )
    })
  })

  it('搜尋的時間照實際範圍說：幾秒到一分鐘（審計 P2-12）', async () => {
    await speak()
    expect(t('search.slow')).toMatch(
      language === 'en' ? /a few seconds to a minute/ : /幾秒到一分鐘/,
    )
  })
})

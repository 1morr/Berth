import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
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
  routeView,
  setupStatus,
  site,
  step,
  tmdbSetup,
} from '../test/fixtures'
import { SetupPage } from './SetupPage'

/**
 * M4 票 104：票 103 的 critique 留下的兩件事。
 *
 * - P1：既有分支同一件事說好幾次（頁 2 做完之後「不改偏好」說五次、探針說三次），要使用者自己留意的那一件
 *   （「torrent 加入時執行外部程式」會觸發）被淹沒。每件事只在一處說，那一件獨立一行。
 * - P2：頁與頁之間、重新整理前後的說法與塗漆一致。
 *
 * 每一條照 zh-Hant 與 en 各跑一次。數「說了幾次」看的是畫面上的字（`placesSaying`），不是 key：
 * 同一件事換一個 key 說第二次一樣算。
 */

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18next.changeLanguage('zh-Hant')
})

const LANGUAGES = ['zh-Hant', 'en'] as const

const STATUS = 'GET /api/setup/status'
const OWNER = 'POST /api/setup/owner'
const QBITTORRENT = 'GET /api/setup/qbittorrent/diff'
const INDEXERS = 'GET /api/setup/indexers'
const JELLYFIN = 'GET /api/setup/jellyfin'
const ROUTES = 'GET /api/setup/routes'
const REREAD = 'POST /api/setup/routes/libraries'
const TMDB = 'GET /api/setup/tmdb'

const t = (key: string, options?: Record<string, unknown>): string =>
  String(i18next.t(key as never, options))

/** 說到 `fact` 的那幾處（一處是一段連續的字，一個文字節點）。 */
function placesOf(places: string[], fact: RegExp): string[] {
  return places.filter((place) => fact.test(place))
}

/**
 * 整頁（主欄、剖面、泊位板）說到 `fact` 的那幾處。同一段字裡換個說法再說一次不算第二處——那是那一段自己的
 * 字數問題；這裡守的是「同一件事散在好幾處」。斷言它的長度，紅的時候看得到是哪幾處。
 */
function placesSaying(fact: RegExp): string[] {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const places: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode())
    places.push(node.textContent ?? '')
  return placesOf(places, fact)
}

describe('placesOf（雙向）', () => {
  const KEEPS = /不改|不寫/
  it('同一件事在兩處說就是兩次', () => {
    expect(placesOf(['Berth 不改你原本的設定。', '全域偏好一個都不寫。'], KEEPS)).toHaveLength(2)
    expect(
      placesOf(['Leaves your settings alone.', 'No preference is written.'], /alone|written/),
    ).toHaveLength(2)
  })

  it('換標點、換斷句、換別的字照樣算一處', () => {
    expect(placesOf(['Berth 不改你原本的設定，只建分類。', '只建分類'], KEEPS)).toHaveLength(1)
    expect(placesOf(['Berth 不改你原本的設定；頁 3 才建', '頁 3'], KEEPS)).toHaveLength(1)
    expect(
      placesOf(['Berth leaves your settings alone; it only adds categories.'], /alone/),
    ).toHaveLength(1)
  })
})

/** 「Berth 不改你的東西」這一類說法（偏好、設定、站、登入）。 */
const KEEPS_YOURS = {
  'zh-Hant': /不改|不寫|沒有改|不碰|不移除|不動/,
  en: /alone|writes no|no preference|changed none|changes none|does not touch|never removes|not remove|already there stay/i,
} as const

/** 說到探針（探測檔、探測 torrent）的句子。 */
const PROBE = { 'zh-Hant': /探測/, en: /probe/i } as const

const EXISTING_JELLYFIN = chosen({
  origin: 'existing',
  base_url: 'http://nas:8096',
  reason: 'setup_completed',
  detail: '12.0.0',
})
const EXISTING_QBITTORRENT = {
  ...ALL_BUNDLED[1],
  origin: 'existing' as const,
  base_url: 'http://nas:8080',
}
const EXISTING_PROWLARR = {
  ...ALL_BUNDLED[2],
  origin: 'existing' as const,
  base_url: 'http://nas:9696',
}

/** 右欄剖面裡某一列的值。 */
async function cutawayValue(title: string, term: string) {
  const heading = await screen.findByRole('heading', { level: 3, name: title })
  return within(heading.closest('section')!).getByText(term).nextElementSibling
}

describe.each(LANGUAGES)('%s', (language) => {
  async function speak() {
    await i18next.changeLanguage(language)
  }

  describe('第 1 點：既有分支每件事只說一次', () => {
    it('頁 2 既有、做完了：「不改你的東西」只在卡片說一次，探針只說一次，外部程式那一句獨立一行', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 3,
            owner: 'owner',
            services: [EXISTING_JELLYFIN, EXISTING_QBITTORRENT],
          }),
        },
        [QBITTORRENT]: {
          body: qbittorrentSetup({
            origin: 'existing',
            base_url: 'http://nas:8080',
            web_ui_login: false,
          }),
        },
      })

      renderInRoute(<SetupPage />, '/setup?step=2')

      expect(await screen.findByText(t('qbittorrent.doneExisting'))).toBeVisible()
      expect(placesSaying(KEEPS_YOURS[language])).toHaveLength(1)
      expect(placesSaying(PROBE[language])).toHaveLength(1)
      // 一個元件只裝這一句：沒有夾在括號裡、沒有和探針那一句黏在一起。
      const external = screen.getByText(t('connect.externalProgram'))
      expect(external).toBeVisible()
      // 表單收著：貼在測試結果（「改位址或憑證」）的正下方。
      expect(external.parentElement?.previousElementSibling).toContainElement(
        screen.getByRole('button', { name: t('connection.edit') }),
      )
    })

    it('頁 2 既有、還沒測：探針與外部程式那一句在測試鍵旁，探針照樣只說一次', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 2, owner: 'owner', services: [EXISTING_JELLYFIN] }),
        },
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.click(
        await screen.findByRole('radio', { name: new RegExp(`^${t('choice.existing.title')}`) }),
      )

      const external = screen.getByText(t('connect.externalProgram'))
      const test = screen.getByRole('button', { name: t('connect.submit') })
      // 同一張表單、緊接在測試鍵之前。
      expect(external.closest('form')).toBe(test.closest('form'))
      expect(external.parentElement?.nextElementSibling).toContainElement(test)
      expect(placesSaying(PROBE[language])).toHaveLength(1)
      expect(placesSaying(KEEPS_YOURS[language])).toHaveLength(1)
    })

    it('頁 1 既有、擁有者成立：「不改」與「換一台等於換擁有者」各說一次', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 2, owner: 'owner', services: [EXISTING_JELLYFIN] }),
        },
      })

      renderInRoute(<SetupPage />, '/setup?step=1')

      expect(await screen.findByText(t('owner.locked'))).toBeVisible()
      expect(placesSaying(KEEPS_YOURS[language])).toHaveLength(1)
      expect(placesSaying(language === 'en' ? /another owner/ : /換擁有者/)).toHaveLength(1)
      expect(
        placesSaying(language === 'en' ? /password is changed/ : /密碼在 Jellyfin 裡改/),
      ).toHaveLength(1)
    })

    it('頁 4 既有、已經有站：「不動你的站」只在卡片說一次', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({
            current_step: 5,
            owner: 'owner',
            services: [EXISTING_JELLYFIN, EXISTING_QBITTORRENT, EXISTING_PROWLARR],
          }),
        },
        [INDEXERS]: {
          body: indexerSetup({
            origin: 'existing',
            base_url: 'http://nas:9696',
            sites: [site(RECOMMENDED[0], 1)],
          }),
        },
        [TMDB]: { body: tmdbSetup() },
      })

      renderInRoute(<SetupPage />, '/setup?step=4')

      expect(await screen.findByText(t('indexer.lede.existing'))).toBeVisible()
      expect(placesSaying(KEEPS_YOURS[language])).toHaveLength(1)
    })
  })

  describe('第 2 點：一致性', () => {
    it('頁 4 還沒選時的標題與頁 1、頁 2 同一個形狀', async () => {
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

      const heading = await screen.findByRole('heading', { level: 2 })
      expect(heading).toHaveTextContent(t('indexer.title.choose'))
      const shape = (key: string, name: string) => t(key).replace(name, '<service>')
      expect(shape('indexer.title.choose', 'Prowlarr')).toBe(
        shape('qbittorrent.title.choose', 'qBittorrent'),
      )
      expect(shape('indexer.title.choose', 'Prowlarr')).toBe(
        shape('owner.title.choose', 'Jellyfin'),
      )
      // lede 不再重複標題那一句。
      expect(screen.getByText(t('indexer.lede.choose'))).not.toHaveTextContent(
        t('indexer.title.choose'),
      )
    })

    it('頁 3 與頁 6 的「已繫上」同一種塗漆：常態不塗', async () => {
      await speak()
      const routes = routeSetup({
        routes: [routeView({ library: 'TV', slug: 'tv' })],
        libraries: routeSetup().libraries.map((row) => ({ ...row, has_route: true })),
        ready: true,
      })
      const page = {
        [ROUTES]: { body: routes },
        [REREAD]: { body: routes },
        [JELLYFIN]: {
          body: jellyfinSetup({
            steps: SEQUENCE_DONE,
            api_key_present: true,
            bundled: jellyfinSetup().bundled.map((row) => ({ ...row, built: true })),
          }),
        },
        [TMDB]: { body: tmdbSetup() },
        [INDEXERS]: { body: indexerSetup() },
        [QBITTORRENT]: { body: qbittorrentSetup() },
      }
      const chip = async () => (await screen.findAllByText(t('routes.health.ok')))[0]!

      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 6, owner: 'skipper', services: ALL_BUNDLED }),
        },
        ...page,
      })
      const { unmount } = renderInRoute(<SetupPage />, '/setup?step=3')
      const routesChip = (await chip()).className
      unmount()
      vi.unstubAllGlobals()

      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 6, owner: 'skipper', services: ALL_BUNDLED }),
        },
        ...page,
      })
      renderInRoute(<SetupPage />, '/setup?step=6')
      await screen.findByRole('heading', { level: 2, name: t('complete.title') })
      const completeChip = (await chip()).className

      expect(completeChip).toBe(routesChip)
      expect(completeChip).not.toMatch(/bg-secured/)
    })

    it('頁 2 套件內做完：工作欄不疊三顆綠章', async () => {
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
            steps: [step('web_ui_password', 'ok', 'skipper')],
            web_ui_username: 'skipper',
            web_ui_login_by_berth: true,
          }),
        },
      })

      renderInRoute(<SetupPage />, '/setup?step=2')

      const heading = await screen.findByRole('heading', {
        level: 2,
        name: t('qbittorrent.title.bundled'),
      })
      await screen.findByText(t('interfaceLogin.qbittorrent.set'))
      const work = heading.parentElement!
      // 連線那一列的「連上了」與登入那一條的「已完成」各一顆，說的是兩件事；不再多一則完成提示（M4 票 104）。
      const painted = [...work.querySelectorAll('.bg-secured')].map((chip) => chip.textContent)
      expect(painted).toEqual([t('connection.state.ok'), t('status.ok')])
    })

    it.each([
      ['頁 2', '/setup?step=2', 'qbittorrent'],
      ['頁 4', '/setup?step=4', 'prowlarr'],
    ] as const)(
      '%s：沿用 Jellyfin 帳密設的登入，重新整理之後照樣說「已沿用」',
      async (_, url, service) => {
        await speak()
        const ours = {
          web_ui_username: 'skipper',
          web_ui_login_by_berth: true,
          web_ui_login_reuses_owner: true,
        }
        stubApi({
          [STATUS]: {
            body: setupStatus({ current_step: 5, owner: 'skipper', services: ALL_BUNDLED }),
          },
          [QBITTORRENT]: {
            body: qbittorrentSetup({ ...ours, steps: [step('web_ui_password', 'ok', 'skipper')] }),
          },
          [INDEXERS]: {
            body: indexerSetup({
              ...ours,
              sites: [site(RECOMMENDED[0], 1)],
              steps: [step('prowlarr_login', 'ok', 'skipper')],
            }),
          },
          [TMDB]: { body: tmdbSetup() },
        })

        // 一個新的分頁：頁 1 帶過來的那一組已經不在記憶體裡。
        renderInRoute(<SetupPage />, url)

        expect(
          await screen.findByText(t('interfaceLogin.carried.set', { owner: 'skipper' })),
        ).toBeVisible()
        expect(
          screen.getByRole('button', { name: t('interfaceLogin.carried.another') }),
        ).toBeVisible()
        expect(screen.queryByText(t(`interfaceLogin.${service}.set`))).not.toBeInTheDocument()
      },
    )

    it.each([
      ['頁 2', '/setup?step=2', 'qbittorrent.cutaway.server'],
      ['頁 4', '/setup?step=4', 'indexer.cutaway.title'],
    ] as const)(
      '%s 的剖面有同一列「介面登入」：套件內說帳號，既有說在它自己的介面上管',
      async (_, url, title) => {
        await speak()
        const login = { web_ui_username: 'skipper', web_ui_login_by_berth: true }
        stubApi({
          [STATUS]: {
            body: setupStatus({ current_step: 5, owner: 'skipper', services: ALL_BUNDLED }),
          },
          [QBITTORRENT]: {
            body: qbittorrentSetup({ ...login, steps: [step('web_ui_password', 'ok', 'skipper')] }),
          },
          [INDEXERS]: { body: indexerSetup({ ...login, sites: [site(RECOMMENDED[0], 1)] }) },
          [TMDB]: { body: tmdbSetup() },
        })
        const { unmount } = renderInRoute(<SetupPage />, url)
        // 那一台讀回來之前是「將設為…」：等它讀回來。
        await waitFor(async () =>
          expect(await cutawayValue(t(title), t('interfaceLogin.cutaway.term'))).toHaveTextContent(
            'skipper',
          ),
        )
        unmount()
        vi.unstubAllGlobals()

        stubApi({
          [STATUS]: {
            body: setupStatus({
              current_step: 5,
              owner: 'owner',
              services: [EXISTING_JELLYFIN, EXISTING_QBITTORRENT, EXISTING_PROWLARR],
            }),
          },
          [QBITTORRENT]: {
            body: qbittorrentSetup({
              origin: 'existing',
              base_url: 'http://nas:8080',
              web_ui_login: false,
            }),
          },
          [INDEXERS]: {
            body: indexerSetup({
              origin: 'existing',
              base_url: 'http://nas:9696',
              sites: [site(RECOMMENDED[0], 1)],
            }),
          },
          [TMDB]: { body: tmdbSetup() },
        })
        renderInRoute(<SetupPage />, url)
        expect(await cutawayValue(t(title), t('interfaceLogin.cutaway.term'))).toHaveTextContent(
          t('interfaceLogin.cutaway.existing'),
        )
      },
    )

    it('頁 1 勾了「也用這組」並送出之後，剖面不再說密碼只交給 Jellyfin', async () => {
      await speak()
      stubApi({
        [STATUS]: { body: setupStatus({ services: [chosen()] }) },
        [OWNER]: {
          body: setupStatus({ current_step: 2, owner: 'skipper', services: [chosen()] }),
        },
      })
      const user = userEvent.setup()

      renderInRoute(<SetupPage />)
      await user.type(await screen.findByLabelText(t('owner.field.username')), 'skipper')
      await user.type(screen.getByLabelText(t('owner.field.password')), 'harbour')
      await user.type(screen.getByLabelText(t('owner.field.confirm')), 'harbour')
      expect(screen.getByRole('checkbox', { name: t('owner.carry.label') })).toBeChecked()
      expect(
        await cutawayValue(t('owner.cutaway.title'), t('owner.cutaway.stored')),
      ).toHaveTextContent(t('owner.cutaway.passwordCarried'))
      await user.click(screen.getByRole('button', { name: t('owner.submit.create') }))

      await screen.findByRole('heading', {
        level: 2,
        name: t('owner.title.owned', { name: 'skipper' }),
      })
      expect(
        await cutawayValue(t('owner.cutaway.title'), t('owner.cutaway.stored')),
      ).toHaveTextContent(new RegExp(`^${t('owner.cutaway.passwordOwned')}$`))
      expect(screen.queryByText(t('owner.cutaway.password'))).not.toBeInTheDocument()
    })

    it('頁 1 套件內鎖住之後：位址怎麼改只由「這裡能做」說，鎖定說明不再說「同一台換了位址可以改」', async () => {
      await speak()
      stubApi({
        [STATUS]: {
          body: setupStatus({ current_step: 2, owner: 'skipper', services: [chosen()] }),
        },
      })

      renderInRoute(<SetupPage />, '/setup?step=1')

      expect(await screen.findByText(t('owner.locked'))).toBeVisible()
      expect(screen.getByText(t('setup.revisit.jellyfin.bundledCan'))).toBeVisible()
      expect(placesSaying(language === 'en' ? /address/i : /位址/)).toHaveLength(1)
    })
  })
})

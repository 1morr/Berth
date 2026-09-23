import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, UNAUTHORIZED, UNCONFIGURED, session, stubApi } from './test/fetch'
import { renderApp } from './test/render'
import { discoverWall, setupStatus } from './test/fixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const HEALTH = 'GET /api/health'
const ME = 'GET /api/auth/me'
const LOGOUT = 'POST /api/auth/logout'

/** 精靈跑完的一台：路由守衛讀 health，精靈頁自己才讀 setup/status。 */
const DONE = { body: HEALTHY }
const PENDING = { body: UNCONFIGURED }
const WIZARD = { body: setupStatus({ completed: true, current_step: 8 }) }
const ADMIN = { body: { name: 'skipper', role: 'admin' } }
const USER = { body: { name: 'deckhand', role: 'user' } }
/** 探索頁是 `/`（票 03）。路由測試只是路過它，所以兩個 feed 都給空牆。 */
const DISCOVER = {
  'GET /api/discover/trending': discoverWall(),
  'GET /api/discover/popular': discoverWall(),
}

describe('路由', () => {
  it('setup 未完成時開 / 會被導向精靈（票 05 驗收）', async () => {
    stubApi({ [STATUS]: { body: setupStatus() }, [HEALTH]: PENDING })

    const { router } = renderApp('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
    expect(await screen.findByText('設定精靈')).toBeInTheDocument()
  })

  it('setup 完成且已登入時 / 是探索頁（票 03：不再導向 /health）', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: ADMIN, ...DISCOVER })

    const { router } = renderApp('/')

    expect(await screen.findByRole('region', { name: '本週趨勢' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('後端連不上時不把人丟到精靈，讓目的地自己說發生什麼事', async () => {
    stubApi({ [HEALTH]: { body: HEALTHY, status: 500 } })

    const { router } = renderApp('/')

    expect(await screen.findAllByText(/讀不到 Berth 後端/)).not.toHaveLength(0)
    expect(router.state.location.pathname).toBe('/')
  })

  it('直接開 /setup 就是精靈', async () => {
    stubApi({ [HEALTH]: PENDING, [STATUS]: { body: setupStatus() } })

    renderApp('/setup')

    expect(await screen.findByRole('banner')).toHaveTextContent('Berth')
    expect(await screen.findByRole('region', { name: '泊位板' })).toBeInTheDocument()
  })
})

describe('門禁', () => {
  it('沒登入就開 / 會被導向登入頁，並記下原本要去的地方', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: UNAUTHORIZED })

    const { router } = renderApp('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/' })
  })

  it('第一次被擋下來時不說「已過期」', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: UNAUTHORIZED })

    renderApp('/')

    expect(await screen.findByLabelText('帳號')).toBeInTheDocument()
    expect(screen.queryByText('工作階段已過期，請重新登入。')).not.toBeInTheDocument()
  })

  it('session 在使用中失效之後，下一次導航就被送回登入頁並說明原因', async () => {
    // 這一條釘住的是「門禁每次都真的問後端」。拿快取放行的話，session 死了以後
    // 前端會若無其事地繼續走下去。
    const backend = session({ name: 'skipper', role: 'admin' })
    stubApi({ [HEALTH]: DONE, [ME]: () => backend.me(), [STATUS]: WIZARD })
    const { router } = renderApp('/setup')
    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))

    backend.signOut()
    await router.navigate({ to: '/' })

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/', expired: true })
    expect(await screen.findByText('工作階段已過期，請重新登入。')).toBeInTheDocument()
  })

  it('已經登入的人不必再看一次登入表單', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: ADMIN })

    const { router } = renderApp('/login?redirect=%2Fhealth')

    await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
  })

  it('setup 跑完之後沒登入就開 /setup 也會被擋', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: UNAUTHORIZED })

    const { router } = renderApp('/setup')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/setup' })
  })
})

describe('角色', () => {
  it('管理員的頁首有設定入口', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: ADMIN, [STATUS]: WIZARD, ...DISCOVER })

    renderApp('/')

    expect(await screen.findByRole('link', { name: '設定' })).toBeInTheDocument()
    expect(screen.getByText('管理員')).toBeInTheDocument()
    expect(screen.getByText('skipper')).toBeInTheDocument()
  })

  it('/settings 轉到服務設定；頁首的「設定」在兩個設定頁都標成當前頁（票 14a）', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: ADMIN, 'GET /api/routes': { body: [] } })

    const { router } = renderApp('/settings')

    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/services'))
    expect(await screen.findByRole('link', { name: '設定' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await router.navigate({ to: '/settings/routes' })
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/routes'))
    expect(screen.getByRole('link', { name: '設定' })).toHaveAttribute('aria-current', 'page')
  })

  it('當前頁只由 aria-current 與 data-status 說，不另外疊一組 class（票 13）', async () => {
    // `activeProps` 的 class 是接在後面的：當前那一格同時帶 `border-rule` 與 `border-rule-strong`，
    // 誰贏看 CSS 的產生順序。當前與否只該差在 TanStack 掛的兩個屬性上，漆由 `data-[status=active]:` 換。
    stubApi({ [HEALTH]: DONE, [ME]: ADMIN, ...DISCOVER })

    renderApp('/')

    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))
    const current = nav.getByRole('link', { name: '探索' })
    const other = nav.getByRole('link', { name: '下載' })

    expect(current).toHaveAttribute('aria-current', 'page')
    expect(other).not.toHaveAttribute('aria-current')
    expect(current).toHaveAttribute('data-status', 'active')
    // 多出來的只有 TanStack 預設的 `active` 標記（這裡沒有任何樣式掛在它上面）。
    expect([...current.classList].filter((name) => !other.classList.contains(name))).toEqual([
      'active',
    ])
  })

  it('非 admin 看不到設定入口，但看得到自己是什麼角色（票 07 驗收）', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: USER, ...DISCOVER })

    renderApp('/')

    expect(await screen.findByText('deckhand')).toBeInTheDocument()
    expect(screen.getByText('使用者')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '設定' })).not.toBeInTheDocument()
  })

  it('非 admin 直接打 /setup 會被送回首頁', async () => {
    stubApi({ [HEALTH]: DONE, [ME]: USER, ...DISCOVER })

    const { router } = renderApp('/setup')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('登出後回到登入頁', async () => {
    const backend = session({ name: 'skipper', role: 'admin' })
    stubApi({
      [HEALTH]: DONE,
      [ME]: () => backend.me(),
      [LOGOUT]: backend.signOut,
      ...DISCOVER,
    })
    const { router } = renderApp('/')

    await userEvent.click(await screen.findByRole('button', { name: '登出' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })
})

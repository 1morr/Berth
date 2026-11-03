import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { WaitingCounts } from '../api/waiting'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { discoverWall } from '../test/fixtures'
import { renderApp } from '../test/render'

/**
 * 頁首（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）：帳號選單的鍵盤與焦點、導覽項上的件數、
 * 區塊的當前頁。導覽列逐角色列齊的那一條在 `router.test.tsx`。
 */

const ADMIN = { body: { name: 'skipper', role: 'admin' } }
const USER = { body: { name: 'deckhand', role: 'user' } }

function waiting(counts: WaitingCounts) {
  return { 'GET /api/waiting': { body: counts } }
}

function render(routes: StubRoutes = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': ADMIN,
    'GET /api/discover/trending': discoverWall(),
    'GET /api/discover/popular': discoverWall(),
    ...routes,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('帳號選單', () => {
  it('鍵盤打得開、Esc 關得掉，焦點回到觸發鍵', async () => {
    render()
    renderApp('/')
    const user = userEvent.setup()
    const trigger = await screen.findByRole('button', { name: '帳號：skipper' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    trigger.focus()
    await user.keyboard('{Enter}')

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveFocus()
    // 下一個 Tab 進到選單的第一項。
    await user.tab()
    expect(screen.getByRole('link', { name: '設定' })).toHaveFocus()

    await user.keyboard('{Escape}')

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: '設定' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('點外面、或 Tab 走出選單就收起', async () => {
    render()
    renderApp('/')
    const user = userEvent.setup()
    const trigger = await screen.findByRole('button', { name: '帳號：skipper' })

    await user.click(trigger)
    await user.click(screen.getByRole('main'))
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)
    // 最後一項是登出；再一個 Tab 就離開選單。
    screen.getByRole('button', { name: '登出' }).focus()
    await user.tab()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('換語言不收：還要看一眼換好了沒', async () => {
    render()
    renderApp('/')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: '帳號：skipper' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(screen.getByRole('button', { name: 'Account: skipper' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    await user.click(screen.getByRole('button', { name: 'ZH' }))
  })

  it('在選單裡的頁面上，觸發鍵說它是當前的區塊；別頁不說', async () => {
    render()
    const { router } = renderApp('/health')

    const trigger = await screen.findByRole('button', { name: '帳號：skipper' })
    expect(trigger).toHaveAttribute('aria-current', 'true')
    // 打開不換漆也不換語意：展開由 `aria-expanded` 說。
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-current', 'true')

    await router.navigate({ to: '/' })
    expect(await screen.findByRole('button', { name: '帳號：skipper' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('說出名字與角色；一般使用者沒有週報', async () => {
    render({ 'GET /api/auth/me': USER })
    renderApp('/')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: '帳號：deckhand' }))

    expect(screen.getByText('使用者')).toBeVisible()
    expect(screen.getByRole('link', { name: '設定' })).toBeVisible()
    expect(screen.getByRole('link', { name: '健康' })).toBeVisible()
    expect(screen.queryByRole('link', { name: '週報' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登出' })).toBeVisible()
  })
})

describe('頁首的件數', () => {
  it('待處理是審核加 Issue，新番是待綁定，用字說出來', async () => {
    render(waiting({ review: 1, issue: 2, rss: 1 }))
    renderApp('/')

    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))

    expect(await nav.findByRole('link', { name: '待處理 3 件' })).toHaveAttribute('href', '/review')
    expect(nav.getByRole('link', { name: '新番 1 件' })).toHaveAttribute('href', '/schedule')
  })

  it('0 件不畫那一塊；一般使用者不問', async () => {
    const api = render(waiting({ review: 0, issue: 0, rss: 0 }))
    renderApp('/')

    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))
    await waitFor(() => expect(api.mock.calls.some(([url]) => url === '/api/waiting')).toBe(true))
    expect(nav.getByRole('link', { name: '待處理' })).toBeVisible()
    expect(nav.getByRole('link', { name: '新番' })).toBeVisible()
  })

  it('一般使用者不問件數（後端是 403）', async () => {
    const api = render({ 'GET /api/auth/me': USER })
    renderApp('/')

    await screen.findByRole('navigation', { name: '主要導覽' })
    expect(api.mock.calls.some(([url]) => url === '/api/waiting')).toBe(false)
  })
})

describe('動作之後重讀件數', () => {
  it('任何動作結束都讓件數失效，不等下一分鐘', async () => {
    let issue = 1
    render({ 'GET /api/waiting': () => ({ body: { review: 0, issue, rss: 0 } }) })
    const { queryClient } = renderApp('/')
    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))
    expect(await nav.findByRole('link', { name: '待處理 1 件' })).toBeVisible()

    issue = 0
    const done = queryClient.getMutationCache().build(queryClient, {
      mutationFn: () => Promise.resolve('resolved'),
    })
    await done.execute(undefined)

    expect(await nav.findByRole('link', { name: '待處理' })).toBeVisible()
  })
})

describe('區塊的當前頁', () => {
  it('在 /issues 上「待處理」是當前區塊，分頁列的 Issue 是當前頁', async () => {
    render({
      ...waiting({ review: 0, issue: 1, rss: 0 }),
      'GET /api/issues': { body: [] },
      'GET /api/reconcile': { body: { current: null, last: null } },
    })
    renderApp('/issues')

    const nav = within(await screen.findByRole('navigation', { name: '主要導覽' }))
    expect(await nav.findByRole('link', { name: '待處理 1 件' })).toHaveAttribute(
      'aria-current',
      'true',
    )

    const tabs = within(screen.getByRole('navigation', { name: '待處理' }))
    expect(tabs.getByRole('link', { name: 'Issue 1 件' })).toHaveAttribute('aria-current', 'page')
    expect(tabs.getByRole('link', { name: '審核' })).not.toHaveAttribute('aria-current')
  })
})

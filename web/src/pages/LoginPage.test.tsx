import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, UNCONFIGURED, session, stubApi } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/health'
const ME = 'GET /api/auth/me'
const LOGIN = 'POST /api/auth/login'
const DONE = { body: HEALTHY }
const ADMIN = { name: 'skipper', role: 'admin' } as const
const LIBRARY = 'f137a2dd21bbc1b99aa5c0f6bf02a805'
/** `/library` 落在第一個媒體庫；那一頁本身打的其他 API 這裡不在乎。 */
const LIBRARIES = {
  'GET /api/inventory': {
    body: [{ id: LIBRARY, name: 'Anime', collection_type: 'tvshows', sorts: [] }],
  },
}

/** 沒有人登入的一台；`signIn` 之後 `GET /auth/me` 才回得出人來。 */
function signedOut() {
  const backend = session()
  return { backend, routes: { [STATUS]: DONE, [ME]: () => backend.me() } }
}

function bodyOf(call: Parameters<typeof fetch>): unknown {
  return JSON.parse(String(call[1]?.body))
}

async function fillIn(username: string, password: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('帳號'), username)
  await user.type(screen.getByLabelText('密碼'), password)
  await user.click(screen.getByRole('button', { name: '登入' }))
}

describe('登入頁', () => {
  // 探索頁只放 TMDB 牆之後（brief §19，M3 票 06），登入後第一個畫面是媒體庫：接著看的兩列在那裡。
  it('打完帳密送出後落到媒體庫', async () => {
    const { backend, routes } = signedOut()
    const stub = stubApi({ ...routes, [LOGIN]: backend.signIn(ADMIN), ...LIBRARIES })
    const { router } = renderApp('/login')

    await fillIn('skipper', 'harbour')

    await waitFor(() => expect(router.state.location.pathname).toBe(`/library/${LIBRARY}`))
    const login = stub.mock.calls.find((call) => call[1]?.method === 'POST')
    expect(bodyOf(login!)).toEqual({ username: 'skipper', password: 'harbour' })
  })

  it('回到原本要去的那一頁，而不是一律回首頁', async () => {
    const { backend, routes } = signedOut()
    stubApi({ ...routes, [LOGIN]: backend.signIn(ADMIN), 'GET /api/setup/status': { body: {} } })
    const { router } = renderApp('/login?redirect=%2Fsetup')

    await fillIn('skipper', 'harbour')

    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
  })

  it('外部網址不算「原本要去的那一頁」', async () => {
    const { backend, routes } = signedOut()
    stubApi({ ...routes, [LOGIN]: backend.signIn(ADMIN), ...LIBRARIES })
    const { router } = renderApp('/login?redirect=https%3A%2F%2Fevil.example')

    await fillIn('skipper', 'harbour')

    await waitFor(() => expect(router.state.location.pathname).toBe(`/library/${LIBRARY}`))
  })

  it('帳密不對時說的是同一句話，不指名是哪一個錯了', async () => {
    stubApi({ ...signedOut().routes, [LOGIN]: { status: 401, body: { detail: 'refused' } } })
    renderApp('/login')

    await fillIn('skipper', 'wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('帳號或密碼不對。')
  })

  it('Jellyfin 連不上時說的是另一件事，而且給得出下一步', async () => {
    stubApi({ ...signedOut().routes, [LOGIN]: { status: 503, body: { detail: 'no jellyfin' } } })
    renderApp('/login')

    await fillIn('skipper', 'harbour')

    expect(await screen.findByRole('alert')).toHaveTextContent('連不上 Jellyfin')
    expect(screen.getByText('docker compose ps jellyfin')).toBeInTheDocument()
  })

  it('其他錯誤不會被說成「密碼不對」', async () => {
    // 被前置代理擋掉的請求如果也說「帳號或密碼不對」，使用者會一直重打其實正確的密碼。
    stubApi({ ...signedOut().routes, [LOGIN]: { status: 502, body: { detail: 'bad gateway' } } })
    renderApp('/login')

    await fillIn('skipper', 'harbour')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('HTTP 502')
    expect(alert).not.toHaveTextContent('帳號或密碼不對')
  })

  it('被拒絕之後焦點回到密碼欄', async () => {
    stubApi({ ...signedOut().routes, [LOGIN]: { status: 401, body: { detail: 'refused' } } })
    renderApp('/login')

    await fillIn('skipper', 'wrong')

    await waitFor(() => expect(screen.getByLabelText('密碼')).toHaveFocus())
  })

  it('被踢出來的人看得到「工作階段已過期」', async () => {
    stubApi(signedOut().routes)

    renderApp('/login?expired=true')

    expect(await screen.findByText('工作階段已過期，請重新登入。')).toBeInTheDocument()
  })

  it('第一次來的人不會被說成過期', async () => {
    stubApi(signedOut().routes)

    renderApp('/login')

    expect(await screen.findByLabelText('帳號')).toBeInTheDocument()
    expect(screen.queryByText('工作階段已過期，請重新登入。')).not.toBeInTheDocument()
  })

  it('說清楚密碼不是 Berth 的', async () => {
    stubApi(signedOut().routes)

    renderApp('/login')

    expect(await screen.findByText(/Berth 沒有自己的密碼/)).toBeInTheDocument()
  })

  it('精靈還沒跑完時 /login 不該存在', async () => {
    stubApi({ [STATUS]: { body: UNCONFIGURED } })

    const { router } = renderApp('/login')

    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
  })
})

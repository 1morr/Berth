import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import { HEALTHY, UNAUTHORIZED, UNCONFIGURED, session, stubApi } from '../test/fetch'
import { chosen, setupStatus } from '../test/fixtures'
import { renderApp } from '../test/render'

/**
 * 對 Berth 自己的 401 / 403，精靈各說各的（M4 票 25，實測 E10-05、E12-11）。原本 403 說「Berth 後端可能
 * 沒在跑」、搶先成立擁有者的 401 說「後端出錯了」——兩句都叫人去查一個活得好好的容器。
 */

const STATUS = 'GET /api/setup/status'
const OWNER = 'POST /api/setup/owner'
const IN_WIZARD = { ...HEALTHY, setup_completed: false }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Berth 自己的 401 / 403', () => {
  it('不是管理員：說精靈只有 Jellyfin 管理員能繼續，給登出；不說後端沒在跑', async () => {
    const backend = session({ name: 'deckhand', role: 'user' })
    stubApi({
      'GET /api/health': { body: IN_WIZARD },
      'GET /api/auth/me': () => backend.me(),
      'POST /api/auth/logout': backend.signOut,
      [STATUS]: { status: 403, body: { detail: 'administrators only' } },
    })
    const user = userEvent.setup()
    const { router } = renderApp('/setup')

    expect(await screen.findByText(/^精靈只有 Jellyfin 管理員能繼續/)).toHaveTextContent('deckhand')
    expect(screen.queryByText(/沒在跑/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '登出' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('擁有者在別處搶先成立：頁 1 送出時說出來，給登入；不說後端出錯了', async () => {
    let owned = false
    stubApi({
      // 這一頁打開時還沒有擁有者；另一個瀏覽器在這段時間成立了它。
      'GET /api/health': () => ({ body: owned ? IN_WIZARD : UNCONFIGURED }),
      'GET /api/auth/me': UNAUTHORIZED,
      // 頁 1：Jellyfin 選好、連上了，擁有者表單在畫面上。
      [STATUS]: { body: setupStatus({ services: [chosen()] }) },
      [OWNER]: () => {
        owned = true
        return { status: 401, body: { detail: 'sign in to continue the setup wizard' } }
      },
    })
    const user = userEvent.setup()
    const { router } = renderApp('/setup')

    await user.type(await screen.findByLabelText('Jellyfin 帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')
    await user.type(screen.getByLabelText('再輸入一次密碼'), 'harbour')
    await user.click(screen.getByRole('button', { name: '建立管理員並登入' }))

    expect(await screen.findByText(/^擁有者已經在別處成立了/)).toBeVisible()
    expect(screen.queryByText(/後端出錯了/)).not.toBeInTheDocument()

    // 登入頁讀的是重問過的 `/health`：快取裡那一份還說沒有擁有者，會把人送回精靈。
    await user.click(screen.getByRole('button', { name: '前往登入' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/setup' })
  })

  it('頁 1 選服務時被搶先也一樣：不說「登入已失效」——這個人從沒登入過', async () => {
    stubApi({
      'GET /api/health': { body: UNCONFIGURED },
      'GET /api/auth/me': UNAUTHORIZED,
      [STATUS]: { body: setupStatus() },
      'POST /api/setup/services/jellyfin': {
        status: 401,
        body: { detail: 'sign in to continue the setup wizard' },
      },
    })
    const user = userEvent.setup()
    renderApp('/setup')

    await user.click(await screen.findByRole('radio', { name: /^套件內/ }))

    expect(await screen.findByText(/^擁有者已經在別處成立了/)).toBeVisible()
    expect(screen.queryByText(/^登入已失效/)).not.toBeInTheDocument()
  })
})

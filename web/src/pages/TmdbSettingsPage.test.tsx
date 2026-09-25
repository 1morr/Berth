import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { step, tmdbSetup } from '../test/fixtures'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const TMDB = 'GET /api/setup/tmdb'
const TEST = 'POST /api/setup/tmdb/test'

/** 精靈第 7 步驗過的那一把。 */
const VERIFIED = tmdbSetup({
  api_key_present: true,
  verified: true,
  steps: [step('configuration', 'ok', 'images: https://image.tmdb.org/t/p/')],
})

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [TMDB]: { body: VERIFIED },
    ...routes,
  })
}

describe('設定 → TMDB', () => {
  /** 票 06h 實走時抓到：精靈與設定頁共用 `TmdbKey`，「精靈的進度存下來了」跟著搬到了設定頁。 */
  it('還沒有驗過的 key 時說去哪裡拿，但不提精靈的進度', async () => {
    render({ [TMDB]: { body: tmdbSetup() } })
    renderApp('/settings/tmdb')

    expect(await screen.findByText(/themoviedb\.org 註冊/)).toBeVisible()
    expect(screen.queryByText(/精靈/)).not.toBeInTheDocument()
  })

  it('頁標題是這一頁唯一的 h1，說得出現在的 key 驗過了', async () => {
    render()
    renderApp('/settings/tmdb')

    expect(await screen.findByRole('heading', { level: 1, name: 'TMDB 設定' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(await screen.findByText('images: https://image.tmdb.org/t/p/')).toBeInTheDocument()
  })

  /**
   * 票 06h 的 audit（WCAG 4.1.3）：結果區塊原本在測試之後才連同結果一起掛上，螢幕閱讀器只念
   * 「已經在」的 live region 裡的變動，所以結果不會被念出來。
   */
  it('結果的 live region 在按測試之前就在', async () => {
    render({ [TMDB]: { body: tmdbSetup() } })
    renderApp('/settings/tmdb')

    const region = await screen.findByTestId('tmdb')
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toBeEmptyDOMElement()
  })

  it('換一把 key：跑精靈第 7 步的同一支命令，結果就在那一條纜繩上（票 06i 驗收）', async () => {
    const stub = render({
      [TEST]: {
        body: tmdbSetup({
          api_key_present: true,
          verified: false,
          steps: [step('configuration', 'failed', '', 'GET /3/configuration: 401 Unauthorized')],
        }),
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/tmdb')

    await user.type(await screen.findByLabelText('你的 TMDB API key'), 'new-key')
    await user.click(screen.getByRole('button', { name: '測試 TMDB' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/setup/tmdb/test')).toBe(true),
    )
    const call = stub.mock.calls.find(([url]) => url === '/api/setup/tmdb/test')!
    expect(JSON.parse(String(call[1]?.body))).toEqual({ api_key: 'new-key' })
    const line = within(await screen.findByTestId('tmdb'))
    expect(await line.findByText('GET /3/configuration: 401 Unauthorized')).toBeInTheDocument()
  })

  it('已經有一把能用的時候，測不過的那一把沒有換掉，畫面說出來', async () => {
    // 後端的規則（`verify_tmdb`）：舊的那一把驗過，新的測不過就不存，`verified` 仍是 true。
    render({
      [TEST]: {
        body: tmdbSetup({
          api_key_present: true,
          verified: true,
          steps: [step('configuration', 'failed', '', 'GET /3/configuration: 401 Unauthorized')],
        }),
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/tmdb')

    await user.type(await screen.findByLabelText('你的 TMDB API key'), 'wrong-key')
    await user.click(screen.getByRole('button', { name: '測試 TMDB' }))

    expect(
      await screen.findByText('這一把測不過，沒有換掉——探索與入庫照舊用原本那一把。'),
    ).toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRouter,
} from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import '../i18n'
import { ApiError } from '../api/client'
import { RequestFailed } from './RequestFailed'

/** 登入連結要路由（`useNavigate`），所以掛一棵只有這一格的樹。 */
function renderFailed(error: unknown, ownerPending = false) {
  const router = createRouter({
    routeTree: createRootRoute({
      component: () => <RequestFailed error={error} ownerPending={ownerPending} />,
    }),
    history: createMemoryHistory(),
  })
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

/** 門禁的 401 / 403 三種各有一句人話（M4 票 25）；需要登入的兩種給登入連結。 */
describe('RequestFailed：Berth 自己的 401 / 403', () => {
  it('未登入（登入失效）：請登入，給登入連結', async () => {
    renderFailed(new ApiError(401, 'POST /setup/tmdb failed with 401'))

    expect(await screen.findByText(/^登入已失效/)).toBeVisible()
    expect(screen.getByRole('button', { name: '前往登入' })).toBeVisible()
  })

  it('擁有者已在別處成立：說出來，給登入連結', async () => {
    renderFailed(new ApiError(401, 'POST /setup/owner failed with 401'), true)

    expect(await screen.findByText(/^擁有者已經在別處成立了/)).toBeVisible()
    expect(screen.getByRole('button', { name: '前往登入' })).toBeVisible()
  })

  it('不是管理員：說只有管理員做得了，不給登入連結（他已經登入了）', async () => {
    renderFailed(new ApiError(403, 'POST /setup/routes failed with 403'))

    expect(await screen.findByText(/^只有 Jellyfin 管理員做得了這件事/)).toBeVisible()
    expect(screen.queryByRole('button', { name: '前往登入' })).not.toBeInTheDocument()
  })

  it('三句各不相同，也都不說後端出錯或沒在跑', async () => {
    const texts = []
    for (const [error, pending] of [
      [new ApiError(401, 'x'), false],
      [new ApiError(401, 'x'), true],
      [new ApiError(403, 'x'), false],
    ] as const) {
      const { unmount } = renderFailed(error, pending)
      const notice = await screen.findByTestId('request-failed')
      texts.push(notice.textContent ?? '')
      expect(notice.textContent).not.toMatch(/出錯了|沒在跑/)
      unmount()
    }
    expect(new Set(texts).size).toBe(3)
  })
})

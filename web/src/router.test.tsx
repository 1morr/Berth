import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubApi } from './test/fetch'
import { renderApp } from './test/render'
import { setupStatus } from './test/setupStatus'

afterEach(() => {
  vi.unstubAllGlobals()
})

const STATUS = 'GET /api/setup/status'
const HEALTH = 'GET /api/health'

describe('路由', () => {
  it('setup 未完成時開 / 會被導向精靈（票 05 驗收）', async () => {
    stubApi({ [STATUS]: { body: setupStatus() }, [HEALTH]: { body: HEALTHY } })

    const { router } = renderApp('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
    expect(await screen.findByText('設定精靈')).toBeInTheDocument()
  })

  it('setup 完成後 / 就留在原地', async () => {
    stubApi({
      [STATUS]: { body: setupStatus({ completed: true, current_step: 8 }) },
      [HEALTH]: { body: HEALTHY },
    })

    const { router } = renderApp('/')

    expect(await screen.findByText('正常')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('後端連不上時不把人丟到精靈，讓目的地自己說發生什麼事', async () => {
    stubApi({ [HEALTH]: { body: HEALTHY, status: 500 } })

    const { router } = renderApp('/')

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(router.state.location.pathname).toBe('/')
  })

  it('直接開 /setup 就是精靈', async () => {
    stubApi({ [STATUS]: { body: setupStatus() } })

    renderApp('/setup')

    expect(await screen.findByRole('banner')).toHaveTextContent('Berth')
    expect(await screen.findByRole('region', { name: '泊位板' })).toBeInTheDocument()
  })
})

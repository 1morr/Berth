import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubJsonResponse } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import { HealthPage } from './HealthPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HealthPage', () => {
  it('shows the backend status once /api/health answers', async () => {
    stubJsonResponse(HEALTHY)

    renderWithProviders(<HealthPage />)

    expect(await screen.findByText('正常')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
  })

  it('calls the API under the /api prefix', async () => {
    const fetchStub = stubJsonResponse(HEALTHY)

    renderWithProviders(<HealthPage />)

    await screen.findByText('正常')
    expect(fetchStub.mock.calls[0][0]).toBe('/api/health')
  })

  it('reports a degraded backend rather than pretending it is fine', async () => {
    stubJsonResponse({ status: 'degraded', version: '0.1.0' })

    renderWithProviders(<HealthPage />)

    expect(await screen.findByText('降級')).toBeInTheDocument()
  })

  it('surfaces an unreachable backend as an alert', async () => {
    stubJsonResponse({ detail: 'Not Found' }, 500)

    renderWithProviders(<HealthPage />)

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})

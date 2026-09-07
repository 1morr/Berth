import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HEALTHY, stubJsonResponse } from './test/fetch'
import { renderApp } from './test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('application shell', () => {
  it('renders the shell and the index route at /', async () => {
    stubJsonResponse(HEALTHY)

    renderApp()

    expect(await screen.findByRole('banner')).toHaveTextContent('Berth')
    expect(await screen.findByText('正常')).toBeInTheDocument()
  })
})

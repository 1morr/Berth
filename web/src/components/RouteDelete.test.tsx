import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { routeView } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { RouteDelete } from './RouteDelete'

const IN_USE = { jobs: 1, ledger_entries: 0, in_use: true }

/** 刪除元件本身的契約（票 14a）。畫面上的流程在 `RouteSettingsPage.test.tsx` 與 `SetupPage.routes.test.tsx`。 */
describe('RouteDelete', () => {
  it('被引用而且還啟用著：給了 onDisable 才有停用鈕', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView()}
        usage={IN_USE}
        onDelete={async () => {}}
        onDisable={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: '停用這條 Route' })).toBeInTheDocument()
  })

  it('沒給 onDisable（精靈）就只說刪不得，不給停用鈕——停用是設定頁的事', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView()}
        usage={IN_USE}
        onDelete={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByText(/刪不得/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '停用這條 Route' })).not.toBeInTheDocument()
  })

  it('已經停用的就不叫人去停用', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView({ enabled: false })}
        usage={IN_USE}
        onDelete={async () => {}}
        onDisable={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByText(/已經停用/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '停用這條 Route' })).not.toBeInTheDocument()
  })
})

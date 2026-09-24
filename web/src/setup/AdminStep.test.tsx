import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { SetupStatus } from '../api/setup'
import { ALL_BUNDLED, detection, setupStatus } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { AdminStep } from './AdminStep'

const ALL_EXISTING = [
  detection({ origin: 'existing', reason: 'setup_completed' }),
  detection({ kind: 'qbittorrent', origin: 'existing', reason: 'connected' }),
  detection({ kind: 'prowlarr', origin: 'existing', reason: 'has_indexers' }),
]

function show(status: SetupStatus, onSubmit = vi.fn()) {
  renderWithProviders(
    <AdminStep status={status} pending={false} failed={false} onSubmit={onSubmit} />,
  )
  return onSubmit
}

/** 剖面裡某一列的值（`<dt>` 是標籤、`<dd>` 是值）。 */
function row(term: RegExp): string {
  const cutaway = screen.getByRole('heading', { name: '將會寫入' }).closest('section')
  const dt = within(cutaway as HTMLElement).getByText(term)
  return dt.nextElementSibling?.textContent ?? ''
}

describe('第 1 步的剖面（票 06c）', () => {
  it('三個服務的標籤都是帳密，值寫帳號與「密碼同上」，不出現密碼本身', async () => {
    show(setupStatus({ services: ALL_BUNDLED, current_step: 3, admin_created: true }))
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('帳號'), 'skipper')
    await user.type(screen.getByLabelText('密碼'), 'harbour')

    expect(row(/Jellyfin 管理員帳密/)).toBe('skipper · 密碼同上')
    expect(row(/qBittorrent WebUI 帳密/)).toBe('skipper · 密碼同上')
    expect(row(/Prowlarr 介面帳密/)).toBe('skipper · 密碼同上')
    expect(screen.queryByText(/harbour/)).toBeNull()
  })

  it('第 2 步還沒偵測時不斷定哪個服務會被寫入', async () => {
    show(setupStatus())
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('帳號'), 'skipper')

    expect(row(/Jellyfin 管理員帳密/)).toBe('skipper · 密碼同上（第 2 步偵測到是套件內的才建立）')
    expect(row(/qBittorrent WebUI 帳密/)).toBe(
      'skipper · 密碼同上（第 2 步偵測到是套件內的才寫入）',
    )
    expect(row(/Prowlarr 介面帳密/)).toBe('skipper · 密碼同上（第 2 步偵測到是套件內的才寫入）')
    expect(screen.getByText(/Jellyfin 是套件內的話/)).toBeVisible()
    expect(screen.getByText(/第 2 步會判斷每個服務是套件內還是你自己的/)).toBeVisible()
  })

  it('探測中與逾時也當成還沒偵測', () => {
    show(
      setupStatus({
        admin_username: 'skipper',
        services: [
          detection({ origin: 'pending' }),
          detection({ kind: 'qbittorrent', origin: 'timeout' }),
        ],
      }),
    )

    expect(row(/Jellyfin 管理員帳密/)).toMatch(/才建立/)
    expect(row(/qBittorrent WebUI 帳密/)).toMatch(/才寫入/)
  })

  it('你自己的服務寫明不建立、不寫入', () => {
    show(
      setupStatus({
        admin_username: 'skipper',
        interface_username: 'skipper',
        jellyfin_owns_account: true,
        services: ALL_EXISTING,
      }),
    )

    expect(row(/Jellyfin 管理員帳密/)).toBe('你自己的服務：用它的管理員登入，不建立')
    expect(row(/qBittorrent WebUI 帳密/)).toBe('你自己的服務，不寫入')
    expect(row(/Prowlarr 介面帳密/)).toBe('你自己的服務，不寫入')
    expect(row(/Berth 管理員/)).toBe('用你 Jellyfin 的管理員登入')
  })

  it('沒勾選時兩個介面都是不套用，不管偵測結果', async () => {
    show(setupStatus({ services: ALL_BUNDLED }))
    const user = userEvent.setup()

    await user.click(screen.getByRole('checkbox'))

    expect(row(/qBittorrent WebUI 帳密/)).toBe('不套用')
    expect(row(/Prowlarr 介面帳密/)).toBe('不套用')
  })
})

describe('帳號屬於 Jellyfin 之後（票 06c）', () => {
  const OWNED = setupStatus({
    current_step: 4,
    admin_created: true,
    admin_username: 'skipper',
    interface_username: 'deckhand',
    jellyfin_owns_account: true,
    services: ALL_BUNDLED,
  })

  it('說出密碼去哪裡改，欄位改的是介面那一組', () => {
    show(OWNED)

    expect(screen.getByRole('heading', { name: 'qBittorrent 與 Prowlarr 介面帳密' })).toBeVisible()
    expect(screen.getByText(/密碼在 Jellyfin 裡改；Berth 的登入就是 Jellyfin 帳號/)).toBeVisible()
    expect(screen.getByText(/回到 qBittorrent 與 Prowlarr 泊位重新套用才會生效/)).toBeVisible()
    expect(screen.getByLabelText('介面帳號')).toHaveValue('deckhand')
    // 第 2 步已經判斷過了，提示不再說「會判斷」。
    expect(screen.queryByText(/第 2 步會判斷/)).toBeNull()
    expect(row(/Jellyfin 管理員帳密/)).toBe('skipper · 已建立，密碼在 Jellyfin 裡改')
    expect(row(/Berth 管理員/)).toBe('skipper')
  })

  it('改介面帳號時 Jellyfin 那一列不跟著動', async () => {
    const onSubmit = show(OWNED)
    const user = userEvent.setup()

    await user.clear(screen.getByLabelText('介面帳號'))
    await user.type(screen.getByLabelText('介面帳號'), 'bosun')
    await user.type(screen.getByLabelText('介面密碼'), 'rope')
    await user.click(screen.getByRole('button', { name: '儲存介面帳密' }))

    expect(row(/Jellyfin 管理員帳密/)).toBe('skipper · 已建立，密碼在 Jellyfin 裡改')
    expect(row(/qBittorrent WebUI 帳密/)).toBe('bosun · 密碼同上')
    expect(onSubmit).toHaveBeenCalledWith({
      username: 'bosun',
      password: 'rope',
      apply_to_services: true,
    })
  })

  it('既有 Jellyfin 說的是它自己的帳號', () => {
    show({ ...OWNED, services: ALL_EXISTING })

    expect(screen.getByText(/Jellyfin 是你自己的服務：Berth 的登入就是它的帳號/)).toBeVisible()
  })
})

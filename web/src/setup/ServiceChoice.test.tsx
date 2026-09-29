import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import type { ServiceKind } from '../api/schemas'
import { chosen, setupStatus } from '../test/fixtures'
import { ServiceChoice } from './ServiceChoice'

function mount(kind: ServiceKind, services = setupStatus().services) {
  return render(
    <ServiceChoice
      kind={kind}
      status={setupStatus({ services })}
      choosing={false}
      retesting={false}
      onChoose={vi.fn()}
      onRetest={vi.fn()}
    />,
  )
}

function floor() {
  return screen.getByTestId('version-floor')
}

describe('「既有」旁的版本下限（M4 票 17）', () => {
  afterEach(async () => {
    await i18next.changeLanguage('zh-Hant')
  })

  it.each([
    ['jellyfin', '版本下限：Jellyfin 12.0'],
    ['qbittorrent', '版本下限：qBittorrent 4.4（Web API 2.8.4）'],
    ['prowlarr', '版本下限：Prowlarr 1.3.2'],
  ] as const)('%s（zh-Hant）', (kind, text) => {
    mount(kind)
    expect(floor()).toHaveTextContent(text)
  })

  it.each([
    ['jellyfin', 'Oldest supported: Jellyfin 12.0'],
    ['qbittorrent', 'Oldest supported: qBittorrent 4.4 (Web API 2.8.4)'],
    ['prowlarr', 'Oldest supported: Prowlarr 1.3.2'],
  ] as const)('%s（en）', async (kind, text) => {
    await i18next.changeLanguage('en')
    mount(kind)
    expect(floor()).toHaveTextContent(text)
  })

  it('Jellyfin 的那一行連到 12.0 的升級注意，另外兩個沒有連結', () => {
    const { unmount } = mount('jellyfin')
    expect(within(floor()).getByRole('link', { name: 'Jellyfin 12.0 升級注意' })).toHaveAttribute(
      'href',
      'https://jellyfin.org/posts/jellyfin-release-12.0/#tl-dr',
    )
    unmount()

    mount('qbittorrent')
    expect(within(floor()).queryByRole('link')).toBeNull()
  })
})

describe('既有表單的 localhost 提示（M4 票 17）', () => {
  it('填 localhost 時位址欄下出提示，改成 host.docker.internal 就收起來', async () => {
    const user = userEvent.setup()
    mount('jellyfin')
    await user.click(screen.getByRole('radio', { name: /既有/ }))

    const address = screen.getByRole('textbox', { name: '位址' })
    await user.type(address, 'http://localhost:38096')
    expect(screen.getByTestId('loopback-hint')).toHaveTextContent('host.docker.internal')
    // 提示掛在欄位的說明上，讀螢幕的人也聽得到。
    expect(address).toHaveAccessibleDescription(/Berth 在容器裡/)

    await user.clear(address)
    await user.type(address, 'http://host.docker.internal:38096')
    expect(screen.queryByTestId('loopback-hint')).toBeNull()
  })

  it('測過的 localhost 連不上時，補法說的是同一句', () => {
    mount('qbittorrent', [
      chosen({
        kind: 'qbittorrent',
        origin: 'existing',
        base_url: 'http://127.0.0.1:38080',
        state: 'failed',
        reason: 'unreachable',
        detail: '',
      }),
    ])

    // 兩處：欄位下那一句跟著正在改的位址走，補法跟著測過的那一個走（改成別的、還沒重測時仍然說它）。
    expect(screen.getAllByText(i18next.t('connect.loopback'))).toHaveLength(2)
  })

  it('連不上而位址不是 localhost：一般的補法', () => {
    mount('qbittorrent', [
      chosen({
        kind: 'qbittorrent',
        origin: 'existing',
        base_url: 'http://192.168.1.10:8080',
        state: 'failed',
        reason: 'unreachable',
        detail: '',
      }),
    ])

    expect(screen.queryByText(i18next.t('connect.loopback'))).toBeNull()
    expect(screen.getByText(i18next.t('connection.fix.address'))).toBeInTheDocument()
  })
})

describe('版本比下限舊（M4 票 17）', () => {
  it('套件內：說拉新的 image，給兩行指令', () => {
    mount('prowlarr', [
      chosen({
        kind: 'prowlarr',
        base_url: 'http://prowlarr:9696',
        state: 'failed',
        reason: 'version_unsupported',
        detail: '1.2.2.2699',
      }),
    ])

    expect(screen.getByText('連得上，但版本比 Berth 支援的下限舊')).toBeInTheDocument()
    expect(screen.getByText(i18next.t('connection.fix.outdatedBundled'))).toBeInTheDocument()
    expect(screen.getByText('docker compose pull prowlarr')).toBeInTheDocument()
  })
})

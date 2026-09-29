import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import type { ServiceKind } from '../api/schemas'
import { chosen, setupStatus } from '../test/fixtures'
import type { ChoiceInput } from '../api/setup'
import { useChoiceDraft } from './choiceDraft'
import { ServiceChoice } from './ServiceChoice'

/** 草稿由頁面持有（`useChoiceDraft`）：這一層就是那個頁面。 */
function Page({
  kind,
  services,
  switchWarning,
  onChoose,
}: {
  kind: ServiceKind
  services: ReturnType<typeof setupStatus>['services']
  switchWarning?: string
  onChoose: (input: ChoiceInput) => void
}) {
  const draft = useChoiceDraft()
  return (
    <>
      <p data-testid="draft">{draft.draft ?? 'none'}</p>
      <ServiceChoice
        kind={kind}
        status={setupStatus({ services })}
        choosing={false}
        retesting={false}
        switchWarning={switchWarning}
        onChoose={onChoose}
        onRetest={vi.fn()}
        {...draft}
      />
    </>
  )
}

function mount(
  kind: ServiceKind,
  services = setupStatus().services,
  { switchWarning, onChoose = vi.fn() }: { switchWarning?: string; onChoose?: () => void } = {},
) {
  return render(
    <Page kind={kind} services={services} switchWarning={switchWarning} onChoose={onChoose} />,
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

describe('換另一格與方向鍵（M4 票 09，票 15 critique / audit 的 P2）', () => {
  const bundled = () => screen.getByRole('radio', { name: /^套件內/ })
  const existing = () => screen.getByRole('radio', { name: /^既有/ })

  it('方向鍵在兩格間移動只改草稿，不送選擇；按「使用套件內」才送', async () => {
    const onChoose = vi.fn()
    const user = userEvent.setup()
    mount('qbittorrent', [], { onChoose })

    bundled().focus()
    await user.keyboard('{ArrowRight}')
    expect(existing()).toBeChecked()
    expect(screen.getByTestId('draft')).toHaveTextContent('existing')
    await user.keyboard('{ArrowLeft}')
    expect(bundled()).toBeChecked()
    expect(screen.getByTestId('draft')).toHaveTextContent('bundled')
    // 瀏覽時焦點留在 radio 上，才走得回另一格。
    expect(bundled()).toHaveFocus()
    expect(onChoose).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '使用套件內的 qBittorrent' }))
    expect(onChoose).toHaveBeenCalledExactlyOnceWith({ origin: 'bundled' })
  })

  it('點一下「套件內」照舊當場存下並測', async () => {
    const onChoose = vi.fn()
    const user = userEvent.setup()
    mount('qbittorrent', [], { onChoose })

    await user.click(bundled())

    expect(onChoose).toHaveBeenCalledExactlyOnceWith({ origin: 'bundled' })
  })

  it('從既有換走：警告只說這一頁要重做，不說 Berth 寫過那一台', async () => {
    const user = userEvent.setup()
    mount(
      'prowlarr',
      [chosen({ kind: 'prowlarr', origin: 'existing', base_url: 'http://nas:9696' })],
      {
        switchWarning: i18next.t('choice.switchWarning.prowlarr'),
      },
    )

    await user.click(bundled())

    const panel = screen.getByRole('group', { name: /換一台 Prowlarr/ })
    expect(panel).toHaveTextContent('Berth 沒動過你那一台的站')
    expect(panel).not.toHaveTextContent('已經加進原本那一台')
  })

  it('從套件內換成既有：後果、表單與取消在同一個確認區，Esc 收起回到原本那一格', async () => {
    const onChoose = vi.fn()
    const user = userEvent.setup()
    mount('prowlarr', [chosen({ kind: 'prowlarr', base_url: 'http://prowlarr:9696' })], {
      switchWarning: i18next.t('choice.switchWarning.prowlarr'),
      onChoose,
    })

    await user.click(existing())

    const panel = screen.getByRole('group', { name: /換一台 Prowlarr/ })
    expect(panel).toHaveFocus()
    expect(panel).toHaveTextContent('已經加進原本那一台的站與登入留在那裡')
    expect(within(panel).getByRole('textbox', { name: '位址' })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group', { name: /換一台 Prowlarr/ })).toBeNull()
    expect(bundled()).toBeChecked()
    expect(bundled()).toHaveFocus()
    expect(onChoose).not.toHaveBeenCalled()
  })

  it('用方向鍵換過去：焦點留在 radio 上瀏覽，Esc 在 radio 上就收得起確認', async () => {
    const onChoose = vi.fn()
    const user = userEvent.setup()
    mount(
      'prowlarr',
      [chosen({ kind: 'prowlarr', origin: 'existing', base_url: 'http://nas:9696' })],
      { switchWarning: i18next.t('choice.switchWarning.prowlarr'), onChoose },
    )

    existing().focus()
    await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('group', { name: /換一台 Prowlarr/ })).toBeInTheDocument()
    expect(bundled()).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group', { name: /換一台 Prowlarr/ })).toBeNull()
    expect(existing()).toBeChecked()
    expect(existing()).toHaveFocus()
    expect(onChoose).not.toHaveBeenCalled()
  })
})

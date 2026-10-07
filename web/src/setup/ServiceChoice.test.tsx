import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import type { ServiceKind } from '../api/schemas'
import { chosen, setupStatus } from '../test/fixtures'
import { stubApi } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import type { ChoiceInput, ChoiceRefusal, Leftovers } from '../api/setup'
import { useChoiceDraft } from './choiceDraft'
import { ServiceChoice } from './ServiceChoice'

/** 草稿由頁面持有（`useChoiceDraft`）：這一層就是那個頁面。 */
function Page({
  kind,
  services,
  switchWarning,
  locked,
  refusal,
  onChoose,
}: {
  kind: ServiceKind
  services: ReturnType<typeof setupStatus>['services']
  switchWarning?: string
  locked?: string
  refusal: ChoiceRefusal | null
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
        locked={locked}
        refusal={refusal}
        requestError={null}
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
  {
    switchWarning,
    locked,
    refusal = null,
    onChoose = vi.fn(),
  }: {
    switchWarning?: string
    locked?: string
    refusal?: ChoiceRefusal | null
    onChoose?: () => void
  } = {},
) {
  return renderWithProviders(
    <Page
      kind={kind}
      services={services}
      switchWarning={switchWarning}
      locked={locked}
      refusal={refusal}
      onChoose={onChoose}
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
    expect(
      screen.getByText('至少要 Prowlarr 1.3.2，套件內那一台是 1.2.2.2699', { exact: false }),
    ).toBeInTheDocument()
    expect(screen.getByText('docker compose pull prowlarr')).toBeInTheDocument()
  })

  /** M4 票 18：10.10.7 原本在測連線時是綠燈、到登入才 502，而且只有英文原文。 */
  it.each([
    ['zh-Hant', '至少要 Jellyfin 12.0，這一台是 10.10.7'],
    ['en', 'Berth needs at least Jellyfin 12.0; this one is 10.10.7'],
  ] as const)('既有 Jellyfin：補法說出下限與它的版本（%s）', async (language, text) => {
    await i18next.changeLanguage(language)
    mount('jellyfin', [
      chosen({
        origin: 'existing',
        base_url: 'http://host.docker.internal:58096',
        state: 'failed',
        reason: 'version_unsupported',
        detail: '10.10.7',
      }),
    ])

    expect(screen.getByText(text, { exact: false })).toBeInTheDocument()
    await i18next.changeLanguage('zh-Hant')
  })
})

describe('擁有者成立之後的 Jellyfin（M4 票 18）', () => {
  const CONNECTED = chosen({
    origin: 'existing',
    base_url: 'http://host.docker.internal:48096',
    reason: 'setup_completed',
  })

  afterEach(async () => {
    await i18next.changeLanguage('zh-Hant')
  })

  it.each([
    ['zh-Hant', '改位址', '改位址或憑證'],
    ['en', 'Change address', 'Change address or credentials'],
  ] as const)(
    'Jellyfin 那一格的鈕只說改位址；qBittorrent 照舊（%s）',
    async (language, jellyfin, other) => {
      await i18next.changeLanguage(language)
      const { unmount } = mount('jellyfin', [CONNECTED], { locked: 'locked' })
      expect(screen.getByRole('button', { name: jellyfin })).toBeVisible()
      expect(screen.queryByRole('button', { name: other })).toBeNull()
      unmount()

      mount('qbittorrent', [
        chosen({ kind: 'qbittorrent', origin: 'existing', reason: 'connected', detail: '5.2.3' }),
      ])
      expect(screen.getByRole('button', { name: other })).toBeVisible()
    },
  )

  it.each([
    ['zh-Hant', '管理員帳密在下一格'],
    ['en', 'the administrator comes next'],
  ] as const)('Jellyfin 的表單不說「管理員帳密在下一格」（%s）', async (language, stale) => {
    await i18next.changeLanguage(language)
    const user = userEvent.setup()
    mount('jellyfin', [CONNECTED], { locked: 'locked' })

    await user.click(screen.getByRole('button', { name: i18next.t('connection.editAddress') }))

    expect(screen.getByText(i18next.t('connect.hint.jellyfin'))).toBeVisible()
    expect(screen.queryByText(stale, { exact: false })).toBeNull()
  })

  it('測試結果那一列不重複「連上了」', () => {
    mount('jellyfin', [CONNECTED])

    expect(screen.getByText('已經有管理員')).toBeVisible()
    expect(screen.queryByText(/連上了，已經有管理員/)).toBeNull()
  })

  it('「改位址」打開的表單有取消：收回去、焦點回到「改位址」，什麼都不送（M4 票 31）', async () => {
    const user = userEvent.setup()
    const onChoose = vi.fn()
    mount('jellyfin', [CONNECTED], { locked: 'locked', onChoose })
    await user.click(screen.getByRole('button', { name: '改位址' }))
    expect(screen.getByRole('textbox', { name: '位址' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: '取消' }))

    expect(screen.queryByRole('textbox', { name: '位址' })).not.toBeInTheDocument()
    // 焦點回到觸發鍵，不掉回 body（DESIGN〈The Focus Follows The Confirm Rule〉）。
    expect(screen.getByRole('button', { name: '改位址' })).toHaveFocus()
    expect(onChoose).not.toHaveBeenCalled()
  })

  it('換到另一台被擋：表單不收，就地說出為什麼沒存', async () => {
    const user = userEvent.setup()
    const { rerender } = mount('jellyfin', [CONNECTED], { locked: 'locked' })
    await user.click(screen.getByRole('button', { name: '改位址' }))
    rerender(
      <Page
        kind="jellyfin"
        services={[CONNECTED]}
        locked="locked"
        refusal={{ reason: 'other_server', detail: 'dc2288726bbe' }}
        onChoose={vi.fn()}
      />,
    )

    // 不拿伺服器名稱呼它：容器裡那是容器 ID（M4 票 31）。
    expect(screen.getByText(/沒有存：這個位址上回答的是另一台 Jellyfin/)).toBeVisible()
    expect(screen.queryByText(/dc2288726bbe/)).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '位址' })).toBeVisible()
  })

  it('連不到的新位址：說認不出是不是同一台，理由用人話', () => {
    mount('jellyfin', [chosen({ ...CONNECTED, state: 'failed', reason: 'unreachable' })], {
      locked: 'locked',
      refusal: { reason: 'unverified', detail: 'unreachable' },
    })

    expect(screen.getByText(/認不出是不是同一台/)).toHaveTextContent('找得到這台主機，但它沒有回應')
  })

  it('存下的位址後面換成另一台：補法說把位址改回去，實測值標成伺服器', () => {
    mount('jellyfin', [
      chosen({ ...CONNECTED, state: 'failed', reason: 'other_server', detail: 'dc2288726bbe' }),
    ])

    expect(screen.getByText(/現在回答的是另一台 Jellyfin。/)).toBeVisible()
    expect(screen.getByText('dc2288726bbe')).toBeVisible()
    expect(screen.getByText('伺服器')).toBeVisible()
  })

  it('Berth 的 key 被撤了：補法說用管理員重新登入', () => {
    mount('jellyfin', [chosen({ ...CONNECTED, state: 'failed', reason: 'auth_required' })])

    expect(screen.getByText(i18next.t('connection.fix.jellyfinKey'))).toBeVisible()
  })
})

describe('套件內那一台不收 Berth 的憑證（M4 票 27）', () => {
  const rejected = {
    origin: 'bundled' as const,
    state: 'failed' as const,
    reason: 'auth_required' as const,
  }

  it('Prowlarr：說掛載的 key，不說 qBittorrent 的免密白名單', () => {
    mount('prowlarr', [
      chosen({ ...rejected, kind: 'prowlarr', base_url: 'http://prowlarr:9696', detail: '' }),
    ])

    expect(screen.getByText(i18next.t('connection.fix.prowlarrMount'))).toBeVisible()
    expect(screen.queryByText(i18next.t('connection.fix.whitelist'))).toBeNull()
    expect(screen.queryByText('docker compose restart prowlarr')).toBeNull()
  })

  it('qBittorrent：說白名單，不給重啟指令（預置腳本補不回關掉的白名單，M4 票 53）', () => {
    mount('qbittorrent', [
      chosen({ ...rejected, kind: 'qbittorrent', base_url: 'http://qbittorrent:8080' }),
    ])

    expect(screen.getByText(i18next.t('connection.fix.whitelist'))).toBeVisible()
    expect(screen.queryByText('docker compose restart qbittorrent')).toBeNull()
    expect(screen.queryByText(i18next.t('connection.fix.prowlarrMount'))).toBeNull()
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

  it('從既有換走：警告只說這一頁要重做', async () => {
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
    expect(panel).toHaveTextContent('換一台 Prowlarr：這一頁要重做。')
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
    expect(panel).toHaveTextContent('換一台 Prowlarr：這一頁要重做。')
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

describe('既有表單測不過：錯誤標在欄位上（M4 票 45）', () => {
  const ADDRESS: Record<ServiceKind, string> = {
    jellyfin: 'http://nas:8096',
    qbittorrent: 'http://nas:8080',
    prowlarr: 'http://nas:9696',
  }

  /** 精靈第一次選既有、按了測試、被拒：什麼都沒存，`services` 還是空的，結論只在拒絕裡。 */
  async function refused(
    kind: ServiceKind,
    reason: NonNullable<ChoiceRefusal['attempt']>['reason'],
    services = setupStatus().services,
  ) {
    const user = userEvent.setup()
    const { rerender } = mount(kind, services)
    await user.click(screen.getByRole('radio', { name: /^既有/ }))
    const attempt = chosen({
      kind,
      origin: 'existing',
      base_url: ADDRESS[kind],
      state: 'failed',
      reason,
      detail: '',
      error: 'GET /raw: 401',
    })
    rerender(
      <Page
        kind={kind}
        services={services}
        refusal={{ reason: 'connection_failed', detail: reason ?? '', attempt }}
        onChoose={vi.fn()}
      />,
    )
  }

  const address = () => screen.getByRole('textbox', { name: '位址' })

  it.each(['jellyfin', 'qbittorrent', 'prowlarr'] as const)(
    '%s 連不上：標在位址欄，aria-describedby 指到那一句',
    async (kind) => {
      await refused(kind, 'unreachable')

      expect(address()).toHaveAttribute('aria-invalid', 'true')
      expect(address()).toHaveAccessibleDescription(i18next.t('connection.fix.address'))
      for (const credential of screen.queryAllByLabelText(/^(帳號|密碼|API key)$/)) {
        expect(credential).not.toHaveAttribute('aria-invalid')
      }
      // 沒存下要說出來；原文收進技術細節。
      expect(screen.getByText(i18next.t('connect.notSaved'))).toBeVisible()
    },
  )

  it('填了 localhost 而連不上：位址欄說那一句（指的是 Berth 自己）', async () => {
    const user = userEvent.setup()
    const { rerender } = mount('qbittorrent')
    await user.click(screen.getByRole('radio', { name: /^既有/ }))
    const attempt = chosen({
      kind: 'qbittorrent',
      origin: 'existing',
      base_url: 'http://localhost:8080',
      state: 'failed',
      reason: 'unreachable',
    })
    rerender(
      <Page
        kind="qbittorrent"
        services={[]}
        refusal={{ reason: 'connection_failed', detail: 'unreachable', attempt }}
        onChoose={vi.fn()}
      />,
    )

    expect(address()).toHaveAttribute('aria-invalid', 'true')
    expect(address()).toHaveAccessibleDescription(i18next.t('connect.loopback'))
  })

  it('qBittorrent 帳密錯：帳號、密碼兩格都標、指到同一句，位址欄不標', async () => {
    await refused('qbittorrent', 'auth_required')

    const said = i18next.t('connection.fix.credentials')
    expect(screen.getByRole('textbox', { name: '帳號' })).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('textbox', { name: '帳號' })).toHaveAccessibleDescription(said)
    expect(screen.getByLabelText('密碼')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('密碼')).toHaveAccessibleDescription(said)
    expect(screen.getAllByText(said)).toHaveLength(1)
    expect(address()).not.toHaveAttribute('aria-invalid')
  })

  it('Prowlarr 的 key 錯：標在 API key 欄', async () => {
    await refused('prowlarr', 'auth_required')

    expect(screen.getByLabelText('API key')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('API key')).toHaveAccessibleDescription(
      i18next.t('connection.fix.prowlarrKey'),
    )
    expect(address()).not.toHaveAttribute('aria-invalid')
  })

  it('版本太舊不屬於哪一格：留在表單裡，欄位都不標', async () => {
    await refused('qbittorrent', 'version_unsupported')

    expect(screen.getByText(/至少要 qBittorrent 4.4/)).toBeVisible()
    expect(address()).not.toHaveAttribute('aria-invalid')
    expect(screen.getByLabelText('密碼')).not.toHaveAttribute('aria-invalid')
  })

  it('連錯的預警看這一次的次數：沒存下也照數', async () => {
    const user = userEvent.setup()
    const { rerender } = mount('qbittorrent')
    await user.click(screen.getByRole('radio', { name: /^既有/ }))
    const attempt = chosen({
      kind: 'qbittorrent',
      origin: 'existing',
      base_url: 'http://nas:8080',
      state: 'failed',
      reason: 'auth_required',
      auth_failures: 3,
    })
    rerender(
      <Page
        kind="qbittorrent"
        services={[]}
        refusal={{ reason: 'connection_failed', detail: 'auth_required', attempt }}
        onChoose={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('密碼')).toHaveAccessibleDescription(/再錯 2 次/)
  })

  it('已經有一台在用：說它照舊在用', async () => {
    const user = userEvent.setup()
    const inUse = chosen({
      kind: 'qbittorrent',
      origin: 'existing',
      base_url: 'http://nas:8080',
      reason: 'connected',
    })
    const { rerender } = mount('qbittorrent', [inUse])
    await user.click(screen.getByRole('button', { name: '改位址或憑證' }))
    rerender(
      <Page
        kind="qbittorrent"
        services={[inUse]}
        refusal={{
          reason: 'connection_failed',
          detail: 'unreachable',
          attempt: chosen({
            ...inUse,
            base_url: 'http://typo:8080',
            state: 'failed',
            reason: 'unreachable',
          }),
        }}
        onChoose={vi.fn()}
      />,
    )

    expect(screen.getByText(i18next.t('connect.notSavedInUse'))).toBeVisible()
    expect(address()).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('qBittorrent 看不到 /data：頁 2 就紅（M4 票 46）', () => {
  const blind = {
    kind: 'qbittorrent' as const,
    state: 'failed' as const,
    reason: 'data_unseen' as const,
    detail: '/data',
    error: 'qBittorrent cannot see /data: it checked the file Berth had just written there',
  }

  it('既有而測不過（沒存下）：表單裡說它沒掛 /data，片段只多加一條，compose 與 docker run 各一', async () => {
    const user = userEvent.setup()
    const { rerender } = mount('qbittorrent', [])
    await user.click(screen.getByRole('radio', { name: /^既有/ }))
    const attempt = chosen({ ...blind, origin: 'existing', base_url: 'http://nas:8080' })
    rerender(
      <Page
        kind="qbittorrent"
        services={[]}
        refusal={{ reason: 'connection_failed', detail: 'data_unseen', attempt }}
        onChoose={vi.fn()}
      />,
    )

    const said = i18next.t('connection.fix.dataUnseen', { root: '/data' })
    expect(screen.getByText(said)).toBeVisible()
    expect(said).toContain('/downloads')
    expect(said).not.toContain('移到')
    expect(screen.getByText(/qbittorrent:\s+volumes:\s+- \$\{DATA_ROOT\}:\/data/)).toBeVisible()
    expect(screen.getByText('-v ${DATA_ROOT}:/data')).toBeVisible()
    // 不屬於哪一格：位址與帳密都不標。
    expect(screen.getByRole('textbox', { name: '位址' })).not.toHaveAttribute('aria-invalid')
  })

  it('既有、存下的那一台重新測試轉紅：連線卡的補法是同一句與同一組片段', () => {
    mount('qbittorrent', [chosen({ ...blind, origin: 'existing', base_url: 'http://nas:8080' })])

    expect(
      screen.getByText(i18next.t('connection.fix.dataUnseen', { root: '/data' })),
    ).toBeVisible()
    expect(screen.getByText(i18next.t('reason.data_unseen'))).toBeVisible()
    expect(screen.getByText('-v ${DATA_ROOT}:/data')).toBeVisible()
  })

  it('套件內：說 compose 裡那一條掛載，片段與 deploy 的一字不差，沒有 docker run', () => {
    mount('qbittorrent', [
      chosen({ ...blind, origin: 'bundled', base_url: 'http://qbittorrent:8080' }),
    ])

    expect(
      screen.getByText(i18next.t('connection.fix.dataUnseenBundled', { root: '/data' })),
    ).toBeVisible()
    expect(screen.getByText(/qbittorrent:\s+volumes:\s+- \$\{DATA_ROOT\}:\/data/)).toBeVisible()
    expect(screen.queryByText('-v ${DATA_ROOT}:/data')).toBeNull()
  })

  it('讀不了是權限、校驗排隊是等一下：兩種都不給掛載片段', () => {
    const { unmount } = mount('qbittorrent', [
      chosen({
        ...blind,
        origin: 'existing',
        base_url: 'http://nas:8080',
        reason: 'data_unreadable',
      }),
    ])
    expect(
      screen.getByText(i18next.t('connection.fix.dataUnreadable', { root: '/data' })),
    ).toBeVisible()
    expect(screen.queryByText('-v ${DATA_ROOT}:/data')).toBeNull()
    unmount()

    mount('qbittorrent', [
      chosen({
        ...blind,
        origin: 'existing',
        base_url: 'http://nas:8080',
        reason: 'data_unsettled',
      }),
    ])
    expect(screen.getByText(i18next.t('connection.fix.dataUnsettled'))).toBeVisible()
  })

  it('既有表單說測試會放探針：不觸發完成時執行，加入時執行會觸發一次；套件內不提', async () => {
    const user = userEvent.setup()
    mount('qbittorrent', [])
    expect(screen.queryByText(/執行外部程式/)).toBeNull()

    await user.click(screen.getByRole('radio', { name: /^既有/ }))

    const hint = screen.getByText(i18next.t('connect.probe', { root: '/data' }))
    expect(hint).toBeVisible()
    expect(hint).toHaveTextContent('不觸發「torrent 完成時執行外部程式」')
    expect(hint).toHaveTextContent('「torrent 加入時執行外部程式」')
  })
})

describe('換台的確認框列出 Berth 在原本那一台留下的東西（M4 票 47）', () => {
  const bundled = () => screen.getByRole('radio', { name: /^套件內/ })
  const existing = () => screen.getByRole('radio', { name: /^既有/ })
  const LEFTOVERS = 'GET /api/setup/services/qbittorrent/leftovers'
  const REMOVE = 'DELETE /api/setup/services/qbittorrent/leftovers/categories'

  function leftovers(overrides: Partial<Leftovers> = {}): Leftovers {
    return {
      kind: 'qbittorrent',
      base_url: 'http://nas:8080',
      reachable: true,
      categories: [
        { name: 'berth-movies', torrents: 2 },
        { name: 'berth-shows', torrents: 0 },
      ],
      sites: [],
      login: '',
      failure: null,
      error: '',
      ...overrides,
    }
  }

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function openSwitch(kind: 'qbittorrent' | 'prowlarr' = 'qbittorrent') {
    const user = userEvent.setup()
    mount(kind, [chosen({ kind, origin: 'existing', base_url: 'http://nas:8080' })], {
      switchWarning: i18next.t(`choice.switchWarning.${kind}`),
    })
    await user.click(bundled())
    return { user, panel: screen.getByRole('group', { name: /換一台/ }) }
  }

  it('列出 berth- 分類與裡面幾個 torrent、Berth 設的登入，給移除空分類的鍵', async () => {
    stubApi({ [LEFTOVERS]: { body: leftovers({ login: 'skipper' }) } })
    const { panel } = await openSwitch()

    const list = await within(panel).findByRole('list')
    expect(within(list).getByText('berth-movies').closest('li')).toHaveTextContent('2 個 torrent')
    expect(within(list).getByText('berth-shows').closest('li')).toHaveTextContent('空的')
    expect(list).toHaveTextContent('Berth 設的介面登入skipper')
    expect(panel).toHaveTextContent('Berth 在原本那一台建的，換了之後留在那裡')
    expect(within(panel).getByRole('button', { name: '移除 1 個空的 berth- 分類' })).toBeEnabled()
  })

  it('移除時鍵停用，移除之後清單換成後端回的那一份並宣告', async () => {
    let release!: () => void
    const removed = new Promise<void>((resolve) => (release = resolve))
    const api = stubApi({
      [LEFTOVERS]: { body: leftovers() },
      [REMOVE]: async () => {
        await removed
        return { body: leftovers({ categories: [{ name: 'berth-movies', torrents: 2 }] }) }
      },
    })
    const { user, panel } = await openSwitch()

    const button = await within(panel).findByRole('button', { name: /移除 1 個空的/ })
    await user.click(button)
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(api.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true)

    release()
    await waitFor(() => expect(within(panel).queryByText('berth-shows')).toBeNull())
    expect(within(panel).getByText('berth-movies')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /移除/ })).toBeNull()
    expect(within(panel).getByRole('status')).toHaveTextContent('空的 berth- 分類已移除')
  })

  it('移除時連不到：說沒有移除，清單不動', async () => {
    stubApi({
      [LEFTOVERS]: { body: leftovers() },
      [REMOVE]: { status: 502, body: { detail: 'qbittorrent: connection refused' } },
    })
    const { user, panel } = await openSwitch()

    await user.click(await within(panel).findByRole('button', { name: /移除 1 個空的/ }))

    expect(await within(panel).findByTestId('request-failed')).toHaveTextContent('沒有移除。')
    expect(within(panel).getByText('berth-shows')).toBeInTheDocument()
    expect(within(panel).getByRole('status')).toHaveTextContent('')
  })

  it('沒有空的分類就沒有移除鍵', async () => {
    stubApi({
      [LEFTOVERS]: { body: leftovers({ categories: [{ name: 'berth-movies', torrents: 2 }] }) },
    })
    const { panel } = await openSwitch()

    await within(panel).findByText('berth-movies')
    expect(within(panel).queryByRole('button', { name: /移除/ })).toBeNull()
  })

  it('連不到原本那一台：說是 Berth 記得的、確認不了，沒有數目也沒有移除鍵', async () => {
    stubApi({
      [LEFTOVERS]: {
        body: leftovers({
          reachable: false,
          categories: [{ name: 'berth-shows', torrents: null }],
          failure: 'unreachable',
          error: 'qbittorrent: connection refused',
        }),
      },
    })
    const { panel } = await openSwitch()

    const row = (await within(panel).findByText('berth-shows')).closest('li')
    expect(row).not.toHaveTextContent('空的')
    expect(panel).toHaveTextContent('連不到原本那一台')
    expect(panel).toHaveTextContent('沒辦法確認現在還在不在')
    expect(within(panel).queryByRole('button', { name: /移除/ })).toBeNull()
    expect(within(panel).getByTestId('technical-details')).toHaveTextContent(
      'qbittorrent: connection refused',
    )
  })

  it('Prowlarr 列出 Berth 加的站，站只列出、不給移除', async () => {
    stubApi({
      'GET /api/setup/services/prowlarr/leftovers': {
        body: leftovers({ kind: 'prowlarr', categories: [], sites: ['Nyaa.si', 'dmhy'] }),
      },
    })
    const user = userEvent.setup()
    mount('prowlarr', [chosen({ kind: 'prowlarr', base_url: 'http://prowlarr:9696' })], {
      switchWarning: i18next.t('choice.switchWarning.prowlarr'),
    })
    await user.click(existing())
    const panel = screen.getByRole('group', { name: /換一台 Prowlarr/ })

    expect(await within(panel).findByText('Nyaa.si、dmhy')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /移除/ })).toBeNull()
  })

  it('原本那一台上沒有 Berth 建的東西時照實說', async () => {
    stubApi({ [LEFTOVERS]: { body: leftovers({ categories: [] }) } })
    const { panel } = await openSwitch()

    expect(await within(panel).findByText('原本那一台上沒有 Berth 建的東西。')).toBeVisible()
  })
})

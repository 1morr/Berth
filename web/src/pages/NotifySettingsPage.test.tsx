import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MyNotify, NotifyBot, NotifyTest } from '../api/notify'
import { HEALTHY, REQUEST_FAILURES, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const READ = 'GET /api/settings/notifications'
const BOT = 'PUT /api/settings/notifications/bot'
const MINE = 'GET /api/me/notifications'
const ME = 'PUT /api/me/notifications'
const TEST = 'POST /api/me/notifications/test'
const BERTH_URL = 'PUT /api/settings/notifications/berth-url'

/** 測試裡一次擺好兩半：`render` 拆成管理員那一份（`NotifyBot`）與「我的」那一份（`MyNotify`）。 */
type Notify = NotifyBot & MyNotify

const INVITE = 'https://discord.com/oauth2/authorize?client_id=1000000000000000001&scope=bot'

const UNSET: Notify = {
  bot_configured: false,
  bot_name: '',
  invite_url: null,
  token_rejected: false,
  unreachable_at: null,
  unreachable_detail: '',
  discord_user_id: '',
  language: 'zh-Hant',
  kinds: ['ready'],
  berth_url: '',
}

const BOT_SET: Notify = {
  bot_configured: true,
  bot_name: 'berth-demo',
  invite_url: INVITE,
  token_rejected: false,
  unreachable_at: null,
  unreachable_detail: '',
  discord_user_id: '',
  language: 'zh-Hant',
  kinds: ['ready'],
  berth_url: '',
}

const READY: Notify = { ...BOT_SET, discord_user_id: '1000000000000000001' }

function refusal(status: number, reason: string, detail = '') {
  return { status, body: { detail: { reason, detail } } }
}

function botOf(notify: Notify): NotifyBot {
  const { bot_configured, bot_name, invite_url, token_rejected, berth_url } = notify
  return { bot_configured, bot_name, invite_url, token_rejected, berth_url }
}

function mineOf(notify: Notify): MyNotify {
  const { bot_configured, bot_name, discord_user_id, language, kinds } = notify
  const { unreachable_at, unreachable_detail } = notify
  return {
    bot_configured,
    bot_name,
    discord_user_id,
    language,
    kinds,
    unreachable_at,
    unreachable_detail,
  }
}

function render(routes: StubRoutes = {}, notify: Notify = UNSET, role: 'admin' | 'user' = 'admin') {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: role === 'admin' ? 'skipper' : 'deckhand', role } },
    [READ]: { body: botOf(notify) },
    [MINE]: { body: mineOf(notify) },
    ...routes,
  })
}

/** 送出去的 body。 */
function sent(stub: ReturnType<typeof stubApi>, key: string): unknown {
  const call = stub.mock.calls.find(
    ([input, init]) => `${init?.method ?? 'GET'} ${String(input)}` === key,
  )
  return JSON.parse(String(call?.[1]?.body))
}

const DELIVERED: NotifyTest = { delivered: true, failure: null, detail: '', retry_after: null }

describe('設定 → 通知', () => {
  it('還沒設定：狀態說還沒設定、沒有邀請連結與移除鍵', async () => {
    render()
    renderApp('/settings/notifications')

    expect(await screen.findByRole('heading', { level: 1, name: '通知設定' })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(await screen.findByText('還沒設定')).toBeVisible()
    expect(screen.getByLabelText('Bot token')).toHaveAttribute('placeholder', '貼上 bot token')
    expect(screen.queryByText('邀請連結')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '移除 token' })).not.toBeInTheDocument()
  })

  it('分頁列：通知在 TMDB 之後，是當前頁', async () => {
    render()
    renderApp('/settings/notifications')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    const names = tabs.getAllByRole('link').map((link) => link.textContent)
    expect(names.at(-2)).toBe('TMDB')
    expect(names.at(-1)).toBe('通知')
    expect(tabs.getByRole('link', { name: '通知' })).toHaveAttribute('data-status', 'active')
  })

  it('已設定：說出 bot 的名字、有邀請連結，欄位空著並說已設定', async () => {
    render({}, BOT_SET)
    renderApp('/settings/notifications')

    expect(await screen.findByText('berth-demo')).toBeVisible()
    expect(screen.getByText('已設定')).toBeVisible()
    expect(screen.getByText(INVITE)).toBeVisible()
    expect(screen.getByRole('link', { name: '開啟邀請連結' })).toHaveAttribute('href', INVITE)
    expect(screen.getByLabelText('Bot token')).toHaveValue('')
    expect(screen.getByLabelText('Bot token')).toHaveAttribute(
      'placeholder',
      '已設定，貼上新的就換掉',
    )
  })

  it('存 token：送出、欄位清空、快取換成回來的狀態', async () => {
    const stub = render({ [BOT]: { body: botOf(BOT_SET) } })
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const field = await screen.findByLabelText('Bot token')
    await user.type(field, ' good-token ')
    await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('berth-demo')).toBeVisible()
    expect(sent(stub, BOT)).toEqual({ token: 'good-token' })
    expect(screen.getByLabelText('Bot token')).toHaveValue('')
    expect(screen.getByText('已儲存。')).toBeVisible()
  })

  it('token 空著按儲存不送出（空字串在後端是清掉）', async () => {
    const stub = render({ [BOT]: { body: botOf(UNSET) } }, BOT_SET)
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    await screen.findByText('berth-demo')
    const form = screen.getByLabelText('Bot token').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('先貼上 bot token。')).toBeVisible()
    expect(stub.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
  })

  it('token_rejected：就地標在欄位上', async () => {
    render({ [BOT]: refusal(422, 'token_rejected', '401 Unauthorized') })
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const field = await screen.findByLabelText('Bot token')
    await user.type(field, 'rejected')
    await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('Discord 不接受這個 token。')).toBeVisible()
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveValue('rejected')
  })

  it('discord_unreachable：說連不上，原文收進技術細節', async () => {
    render({ [BOT]: refusal(502, 'discord_unreachable', 'ConnectError: boom') })
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const field = await screen.findByLabelText('Bot token')
    await user.type(field, 'some-token')
    await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText(/問不到 Discord，token 沒有存下來/)).toBeVisible()
    expect(screen.getByText('ConnectError: boom')).toBeInTheDocument()
    expect(screen.getByTestId('technical-details')).not.toHaveAttribute('open')
  })

  it('移除 token：就地二次確認，確認才送空字串', async () => {
    const stub = render({ [BOT]: { body: botOf(UNSET) } }, BOT_SET)
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    await user.click(await screen.findByRole('button', { name: '移除 token' }))
    expect(stub.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
    expect(screen.getByText(/移除之後 Berth 不再傳任何通知/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: '確定移除' }))

    expect(await screen.findByText('token 已移除。')).toBeVisible()
    expect(sent(stub, BOT)).toEqual({ token: '' })
    expect(screen.getByText('還沒設定')).toBeVisible()
  })

  it('先存再移除：狀態句說的是最後一個動作', async () => {
    // 假後端照送來的 token 回：空字串是清掉。
    render({
      [BOT]: (init) => ({
        body: botOf(JSON.parse(String(init?.body)).token ? BOT_SET : UNSET),
      }),
    })
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const field = await screen.findByLabelText('Bot token')
    await user.type(field, 'good-token')
    await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))
    expect(await screen.findByText('已儲存。')).toBeVisible()

    await user.click(screen.getByRole('button', { name: '移除 token' }))
    await user.click(screen.getByRole('button', { name: '確定移除' }))

    expect(await screen.findByText('token 已移除。')).toBeVisible()
    expect(screen.queryByText('已儲存。')).not.toBeInTheDocument()
  })

  it('存 ID：送出當下的介面語言', async () => {
    const stub = render({ [ME]: { body: mineOf(READY) } }, BOT_SET)
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    expect(
      await screen.findByText(/通知用目前的介面語言（中文）寫；切換介面語言後再按一次儲存就換。/),
    ).toBeVisible()
    await user.type(screen.getByLabelText('Discord 使用者 ID'), '1000000000000000001')
    await user.click(
      within(screen.getByLabelText('Discord 使用者 ID').closest('form')!).getByRole('button', {
        name: '儲存',
      }),
    )

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toEqual({
      discord_user_id: '1000000000000000001',
      language: 'zh-Hant',
      kinds: ['ready'],
    })
  })

  it('英文介面：說通知用英文寫，存下去的語言是 en', async () => {
    await i18next.changeLanguage('en')
    try {
      const stub = render({ [ME]: { body: mineOf({ ...READY, language: 'en' }) } }, BOT_SET)
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Notification settings' }),
      ).toBeVisible()
      expect(
        await screen.findByText(
          /Notifications are written in the current interface language \(English\)/,
        ),
      ).toBeVisible()
      await user.type(screen.getByLabelText('Discord user ID'), '1000000000000000001')
      await user.click(
        within(screen.getByLabelText('Discord user ID').closest('form')!).getByRole('button', {
          name: 'Save',
        }),
      )

      await waitFor(() =>
        expect(sent(stub, ME)).toEqual({
          discord_user_id: '1000000000000000001',
          language: 'en',
          kinds: ['ready'],
        }),
      )
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('已存的語言與現在的介面不同時說出來', async () => {
    render({}, { ...READY, language: 'en' })
    renderApp('/settings/notifications')

    expect(await screen.findByText(/現在存的是 English/)).toBeVisible()
  })

  it('discord_id_invalid：標在欄位上', async () => {
    render({ [ME]: refusal(422, 'discord_id_invalid') }, BOT_SET)
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const field = await screen.findByLabelText('Discord 使用者 ID')
    await user.type(field, '123')
    await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('要是 17 到 20 位數字的 Discord 使用者 ID。')).toBeVisible()
    expect(field).toHaveAttribute('aria-invalid', 'true')
  })

  describe('Berth 的網址', () => {
    it('沒存過：預填現在開著的網址，並說按儲存才算數', async () => {
      const stub = render()
      renderApp('/settings/notifications')

      const field = await screen.findByLabelText('Berth 的網址')
      expect(field).toHaveValue(window.location.origin)
      expect(screen.getByText(/還沒儲存/)).toBeVisible()
      // 預填不是存：打開頁面不送任何寫入。
      expect(stub.mock.calls.some(([input]) => String(input).endsWith('/berth-url'))).toBe(false)
    })

    it('存過：顯示存的值，說通知的連結開在那裡', async () => {
      render({}, { ...UNSET, berth_url: 'https://berth.example.com' })
      renderApp('/settings/notifications')

      expect(await screen.findByLabelText('Berth 的網址')).toHaveValue('https://berth.example.com')
      expect(screen.getByText(/通知裡的連結開在 https:\/\/berth\.example\.com/)).toBeVisible()
      expect(screen.queryByText(/還沒儲存/)).not.toBeInTheDocument()
    })

    it('儲存：送出欄位的值、換成回來的狀態', async () => {
      const saved = botOf({ ...UNSET, berth_url: 'https://berth.example.com' })
      const stub = render({ [BERTH_URL]: { body: saved } })
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      const field = await screen.findByLabelText('Berth 的網址')
      await user.clear(field)
      await user.type(field, 'https://berth.example.com/')
      await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

      expect(
        await screen.findByText(/通知裡的連結開在 https:\/\/berth\.example\.com/),
      ).toBeVisible()
      expect(sent(stub, BERTH_URL)).toEqual({ berth_url: 'https://berth.example.com/' })
      expect(field).toHaveValue('https://berth.example.com')
    })

    it('不是 http(s) 的完整網址（422）：欄位下說原因', async () => {
      render({
        [BERTH_URL]: refusal(422, 'berth_url_invalid', "'berth.local' is not an http(s) address"),
      })
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      const field = await screen.findByLabelText('Berth 的網址')
      await user.clear(field)
      await user.type(field, 'berth.local')
      await user.click(within(field.closest('form')!).getByRole('button', { name: '儲存' }))

      expect(
        await screen.findByText(
          '要是 http:// 或 https:// 開頭、不帶 ? 或 # 的完整網址，例如 https://berth.example.com。',
        ),
      ).toBeVisible()
      expect(field).toHaveAttribute('aria-invalid', 'true')
      expect(field).toHaveValue('berth.local')
    })

    it('en：預填的說明', async () => {
      await i18next.changeLanguage('en')
      try {
        render()
        renderApp('/settings/notifications')

        expect(await screen.findByLabelText('Berth address')).toHaveValue(window.location.origin)
        expect(screen.getByText(/Not saved yet/)).toBeVisible()
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })
  })

  describe('測試鍵', () => {
    it.each([
      ['缺 bot 與 ID', UNSET, '要先設定 Discord bot，並填你的 Discord ID。'],
      ['缺 bot', { ...UNSET, discord_user_id: '1000000000000000001' }, '要先設定 Discord bot。'],
      ['缺 ID', BOT_SET, '要先填你的 Discord ID 並儲存。'],
    ])('%s：aria-disabled、說缺什麼、按了不送', async (_name, notify, missing) => {
      const stub = render({ [TEST]: { body: DELIVERED } }, notify)
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      const button = await screen.findByRole('button', { name: '送一則測試訊息給我' })
      expect(button).toHaveAttribute('aria-disabled', 'true')
      expect(button).toHaveAccessibleDescription(missing)
      await user.click(button)
      expect(stub.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    })

    it('改了 ID 還沒存：測的會是舊的那一個，所以先叫人儲存、按了不送（M4 票 132）', async () => {
      const stub = render({ [TEST]: { body: DELIVERED } }, READY)
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      const field = await screen.findByRole('textbox', { name: 'Discord 使用者 ID' })
      await user.clear(field)
      await user.type(field, '1000000000000000404')
      const button = screen.getByRole('button', { name: '送一則測試訊息給我' })
      expect(button).toHaveAttribute('aria-disabled', 'true')
      expect(button).toHaveAccessibleDescription('先儲存你改過的 Discord ID，再測試。')
      await user.click(button)
      expect(stub.mock.calls.some(([url]) => String(url).endsWith('/test'))).toBe(false)

      // 改回存著的那一個（前後空白不算改）：又能按。
      await user.clear(field)
      await user.type(field, ' 1000000000000000001 ')
      expect(button).not.toHaveAttribute('aria-disabled')
    })

    it('齊了就能按，結果的 live region 在按之前就在', async () => {
      render({ [TEST]: { body: DELIVERED } }, READY)
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      const button = await screen.findByRole('button', { name: '送一則測試訊息給我' })
      const region = button.parentElement!.querySelector('[aria-live="polite"]')!
      expect(region).toBeEmptyDOMElement()
      expect(button).not.toHaveAttribute('aria-disabled')

      await user.click(button)

      expect(await within(region as HTMLElement).findByText('已送出')).toBeVisible()
      expect(within(region as HTMLElement).getByText('看看 Discord 的私訊。')).toBeVisible()
    })

    it('recipient_unreachable：兩個補法一起說，原文在技術細節', async () => {
      render(
        {
          [TEST]: {
            body: {
              delivered: false,
              failure: 'recipient_unreachable',
              detail: '403 Forbidden: Cannot send messages to this user (50007)',
              retry_after: null,
            } satisfies NotifyTest,
          },
        },
        READY,
      )
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      await user.click(await screen.findByRole('button', { name: '送一則測試訊息給我' }))

      expect(await screen.findByText(/把 bot 加進你所在的伺服器/)).toBeVisible()
      expect(screen.getByText(/打開「私人訊息」/)).toBeVisible()
      expect(screen.getByText(/403 Forbidden/)).toBeInTheDocument()
      expect(screen.getByTestId('technical-details')).not.toHaveAttribute('open')
    })

    it('rate_limited：有秒數就說秒數', async () => {
      render(
        {
          [TEST]: {
            body: {
              delivered: false,
              failure: 'rate_limited',
              detail: '',
              retry_after: 2.4,
            } satisfies NotifyTest,
          },
        },
        READY,
      )
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      await user.click(await screen.findByRole('button', { name: '送一則測試訊息給我' }))

      expect(await screen.findByText('等 3 秒再按一次。')).toBeVisible()
    })

    it.each([
      ['unauthorized', /Discord 不接受這個 bot token/],
      ['rejected', /Discord 不收這則訊息/],
      ['unavailable', /Discord 暫時出錯/],
    ] as const)('%s 有自己的一句話', async (failure, text) => {
      render(
        {
          [TEST]: {
            body: {
              delivered: false,
              failure,
              detail: 'x',
              retry_after: null,
            } satisfies NotifyTest,
          },
        },
        READY,
      )
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      await user.click(await screen.findByRole('button', { name: '送一則測試訊息給我' }))

      expect(await screen.findByText(text)).toBeVisible()
    })

    it('英文介面：recipient_unreachable 的兩個補法', async () => {
      await i18next.changeLanguage('en')
      try {
        render(
          {
            [TEST]: {
              body: {
                delivered: false,
                failure: 'recipient_unreachable',
                detail: '',
                retry_after: null,
              } satisfies NotifyTest,
            },
          },
          READY,
        )
        const user = userEvent.setup()
        renderApp('/settings/notifications')

        await user.click(await screen.findByRole('button', { name: 'Send me a test message' }))

        expect(await screen.findByText(/add the bot to a server you are in/)).toBeVisible()
        expect(screen.getByText(/turn on “Direct Messages”/)).toBeVisible()
      } finally {
        await i18next.changeLanguage('zh-Hant')
      }
    })

    it('bot_missing（409）：就地說還沒設定', async () => {
      render({ [TEST]: refusal(409, 'bot_missing') }, READY)
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      await user.click(await screen.findByRole('button', { name: '送一則測試訊息給我' }))

      expect(await screen.findByText('還沒設定 Discord bot。')).toBeVisible()
    })
  })

  it('token_rejected：bot 區塊說通知暫停、要換新 token', async () => {
    render({}, { ...BOT_SET, token_rejected: true })
    renderApp('/settings/notifications')

    const bot = within(await screen.findByRole('region', { name: 'Discord bot' }))
    expect(await bot.findByText('已暫停')).toBeVisible()
    expect(bot.getByText(/Discord 不再接受存著的這個 token，通知暫停送出/)).toBeVisible()
  })

  it('token 沒被拒：沒有暫停那一句', async () => {
    render({}, BOT_SET)
    renderApp('/settings/notifications')

    await screen.findByText('berth-demo')
    expect(screen.queryByText('已暫停')).not.toBeInTheDocument()
  })

  describe('收件人到不了（票 128）', () => {
    const UNREACHABLE: Notify = {
      ...READY,
      unreachable_at: '2026-10-21T08:00:00Z',
      unreachable_detail: '403 Forbidden: Cannot send messages to this user (50278)',
    }

    it('我的 Discord 說出原因、兩個補法、重試那一句（含測試鍵的名字），原文收進技術細節', async () => {
      render({}, UNREACHABLE)
      renderApp('/settings/notifications')

      const me = within(await screen.findByRole('region', { name: '我的通知' }))
      expect(await me.findByText('送不到')).toBeVisible()
      expect(me.getByText(/上次送給你的通知沒送到/)).toBeVisible()
      expect(me.getByText(/把 bot 加進你所在的伺服器/)).toBeVisible()
      expect(me.getByText(/打開「私人訊息」/)).toBeVisible()
      expect(
        me.getByText('補好、儲存之後按下面的「送一則測試訊息給我」：送到了，這一句就會收掉。'),
      ).toBeVisible()
      expect(me.getByText(/50278/)).toBeInTheDocument()
      expect(me.getByTestId('technical-details')).not.toHaveAttribute('open')
    })

    it('沒有 unreachable_at：不說', async () => {
      render({}, READY)
      renderApp('/settings/notifications')

      await screen.findByText('berth-demo')
      expect(screen.queryByText('送不到')).not.toBeInTheDocument()
    })

    it('按測試送到了：重讀 notify，那一句消失', async () => {
      let reads = 0
      const stub = render(
        {
          [MINE]: () => ({ body: mineOf(reads++ === 0 ? UNREACHABLE : READY) }),
          [TEST]: { body: DELIVERED },
        },
        READY,
      )
      const user = userEvent.setup()
      renderApp('/settings/notifications')

      expect(await screen.findByText('送不到')).toBeVisible()
      await user.click(screen.getByRole('button', { name: '送一則測試訊息給我' }))

      await waitFor(() => expect(screen.queryByText('送不到')).not.toBeInTheDocument())
      expect(screen.getByText('已送出')).toBeVisible()
      const reread = stub.mock.calls.filter(([input]) => String(input) === '/api/me/notifications')
      expect(reread).toHaveLength(2)
    })
  })

  it.each(REQUEST_FAILURES)(
    '讀取失敗（%s）：說這一次請求為什麼沒成',
    async (_name, failure, text) => {
      render({ [MINE]: failure })
      renderApp('/settings/notifications')

      expect(await screen.findByText(text)).toBeVisible()
      expect(screen.getByText(/讀不到通知設定/)).toBeVisible()
    },
  )
})

describe('要收的通知（M4 票 125）', () => {
  it('勾選照存的那一份，與 ID 同一個儲存鍵送出', async () => {
    const stub = render({ [ME]: { body: mineOf({ ...READY, kinds: ['downloading'] }) } }, READY)
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const kinds = within(await screen.findByRole('group', { name: '要收的通知' }))
    expect(kinds.getByRole('checkbox', { name: '可以看了' })).toBeChecked()
    expect(kinds.getByRole('checkbox', { name: '正在下載' })).not.toBeChecked()
    expect(kinds.getByRole('checkbox', { name: '可以看了' })).toHaveAccessibleDescription(
      /同一部作品 5 分鐘內的幾批合成一則/,
    )

    await user.click(kinds.getByRole('checkbox', { name: '正在下載' }))
    await user.click(kinds.getByRole('checkbox', { name: '可以看了' }))
    const form = screen.getByLabelText('Discord 使用者 ID').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toEqual({
      discord_user_id: '1000000000000000001',
      language: 'zh-Hant',
      kinds: ['downloading'],
    })
    expect(kinds.getByRole('checkbox', { name: '正在下載' })).toBeChecked()
  })

  it('en：兩種的名字', async () => {
    await i18next.changeLanguage('en')
    try {
      render({}, READY)
      renderApp('/settings/notifications')

      const kinds = within(await screen.findByRole('group', { name: 'Notify me about' }))
      expect(kinds.getByRole('checkbox', { name: 'Ready to watch' })).toBeChecked()
      expect(kinds.getByRole('checkbox', { name: 'Downloading' })).not.toBeChecked()
      expect(screen.getByRole('region', { name: 'My notifications' })).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

describe('有 N 件等你處理（M4 票 127）', () => {
  it('管理員看得到，勾了會一起送出', async () => {
    const stub = render(
      { [ME]: { body: mineOf({ ...READY, kinds: ['ready', 'waiting'] }) } },
      { ...READY, kinds: ['ready'] },
    )
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const kinds = within(await screen.findByRole('group', { name: '要收的通知' }))
    const waiting = await kinds.findByRole('checkbox', { name: '有 N 件等你處理' })
    expect(waiting).not.toBeChecked()
    expect(waiting).toHaveAccessibleDescription(/只有管理員收得到/)

    await user.click(waiting)
    const form = screen.getByLabelText('Discord 使用者 ID').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toMatchObject({ kinds: ['ready', 'waiting'] })
  })

  it('一般使用者沒有這一格，存的時候也不送', async () => {
    const stub = render(
      { [ME]: { body: mineOf({ ...READY, kinds: ['ready'] }) } },
      { ...READY, kinds: ['ready', 'waiting'] },
      'user',
    )
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const kinds = within(await screen.findByRole('group', { name: '要收的通知' }))
    expect(kinds.getByRole('checkbox', { name: '可以看了' })).toBeChecked()
    expect(kinds.queryByRole('checkbox', { name: '有 N 件等你處理' })).not.toBeInTheDocument()

    const form = screen.getByLabelText('Discord 使用者 ID').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toMatchObject({ kinds: ['ready'] })
  })
})

describe('週報（M4 票 131）', () => {
  it('管理員看得到，勾了會一起送出', async () => {
    const stub = render(
      { [ME]: { body: mineOf({ ...READY, kinds: ['ready', 'weekly'] }) } },
      { ...READY, kinds: ['ready'] },
    )
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const kinds = within(await screen.findByRole('group', { name: '要收的通知' }))
    const weekly = await kinds.findByRole('checkbox', { name: '週報' })
    expect(weekly).not.toBeChecked()
    expect(weekly).toHaveAccessibleDescription(/每週一早上：這一週入庫了什麼、修了什麼/)

    await user.click(weekly)
    const form = screen.getByLabelText('Discord 使用者 ID').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toMatchObject({ kinds: ['ready', 'weekly'] })
  })

  it('一般使用者沒有這一格，存的時候也不送', async () => {
    const stub = render(
      { [ME]: { body: mineOf({ ...READY, kinds: ['ready'] }) } },
      { ...READY, kinds: ['ready', 'weekly'] },
      'user',
    )
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    const kinds = within(await screen.findByRole('group', { name: '要收的通知' }))
    expect(kinds.getByRole('checkbox', { name: '可以看了' })).toBeChecked()
    expect(kinds.queryByRole('checkbox', { name: '週報' })).not.toBeInTheDocument()

    const form = screen.getByLabelText('Discord 使用者 ID').closest('form')!
    await user.click(within(form).getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, ME)).toMatchObject({ kinds: ['ready'] })
  })
})

describe('一般使用者（M4 票 125）', () => {
  it('只看得到自己的那一半：沒有分頁列、bot、Berth 的網址，也不讀管理員那一份', async () => {
    const stub = render({}, READY, 'user')
    renderApp('/settings/notifications')

    expect(await screen.findByRole('region', { name: '我的通知' })).toBeVisible()
    expect(screen.getByRole('region', { name: '測試' })).toBeVisible()
    expect(screen.getByText(/勾要收的通知，再按測試/)).toBeVisible()
    expect(screen.queryByRole('navigation', { name: '設定' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Discord bot' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Bot token')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Berth 的網址')).not.toBeInTheDocument()
    expect(screen.queryByText(INVITE)).not.toBeInTheDocument()
    expect(stub.mock.calls.some(([input]) => String(input) === '/api/settings/notifications')).toBe(
      false,
    )
  })

  it('私訊從哪一個 bot 來', async () => {
    render({}, READY, 'user')
    renderApp('/settings/notifications')

    expect(await screen.findByText('私訊會從 Discord 上的 berth-demo 傳來。')).toBeVisible()
  })

  it('bot 還沒設定：測試鍵說管理員還沒設，不叫他自己去設', async () => {
    render({}, { ...UNSET, discord_user_id: '1000000000000000001' }, 'user')
    renderApp('/settings/notifications')

    const button = await screen.findByRole('button', { name: '送一則測試訊息給我' })
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).toHaveAccessibleDescription('管理員還沒設定 Discord bot，設好之後才測得了。')
  })

  it.each([
    ['recipient_unreachable', /請管理員把 bot 加進你所在的伺服器/],
    ['unauthorized', /請管理員到 Developer Portal 換一個新的 token/],
  ] as const)('%s：補法說找管理員', async (failure, fix) => {
    render(
      {
        [TEST]: {
          body: { delivered: false, failure, detail: 'x', retry_after: null } satisfies NotifyTest,
        },
      },
      READY,
      'user',
    )
    const user = userEvent.setup()
    renderApp('/settings/notifications')

    await user.click(await screen.findByRole('button', { name: '送一則測試訊息給我' }))

    expect(await screen.findByText(fix)).toBeVisible()
    expect(screen.queryByText(/用邀請連結/)).not.toBeInTheDocument()
  })
})

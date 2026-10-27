import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiSettings, AiTest } from '../api/ai'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const READ = 'GET /api/settings/ai'
const SAVE = 'PUT /api/settings/ai'
const TEST = 'POST /api/settings/ai/test'

const SONNET_PRICE = {
  input: '2',
  output: '10',
  cache_read: '0.10',
  cache_write: '2.5',
  verified: '2026-10-27',
}

const UNSET: AiSettings = {
  enabled: false,
  provider: 'anthropic',
  anthropic: { base_url: '', model: '', has_key: false, price: null },
  openai: { base_url: '', model: '', has_key: false, price: null },
  has_tavily_key: false,
  known_models: ['claude-haiku-5-5', 'claude-sonnet-5-5', 'deepseek-flash'],
}

/** 兩種都填過、現在用 Anthropic 而且開著。 */
const IN_USE: AiSettings = {
  ...UNSET,
  enabled: true,
  anthropic: { base_url: '', model: 'claude-sonnet-5-5', has_key: true, price: SONNET_PRICE },
  openai: {
    base_url: 'https://api.deepseek.com',
    model: 'some-local-model',
    has_key: true,
    price: null,
  },
}

const CONNECTED: AiTest = {
  ok: true,
  failure: null,
  status: null,
  detail: '',
  model: 'claude-sonnet-5-5-20261001',
}

function refusal(status: number, reason: string, detail = '') {
  return { status, body: { detail: { reason, detail } } }
}

function render(routes: StubRoutes = {}, ai: AiSettings = UNSET) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [READ]: { body: ai },
    ...routes,
  })
}

/** 送出去的 body（同一個端點打了好幾次時取最後一次）。 */
function sent(stub: ReturnType<typeof stubApi>, key: string): unknown {
  const call = stub.mock.calls.findLast(
    ([input, init]) => `${init?.method ?? 'GET'} ${String(input)}` === key,
  )
  return JSON.parse(String(call?.[1]?.body))
}

function calls(stub: ReturnType<typeof stubApi>, key: string): number {
  return stub.mock.calls.filter(
    ([input, init]) => `${init?.method ?? 'GET'} ${String(input)}` === key,
  ).length
}

describe('設定 → AI', () => {
  it('分頁列：AI 在通知與用量之間，是當前頁', async () => {
    render()
    renderApp('/settings/ai')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    const names = tabs.getAllByRole('link').map((link) => link.textContent)
    expect(names.slice(-3)).toEqual(['通知', 'AI', '用量'])
    expect(tabs.getByRole('link', { name: 'AI' })).toHaveAttribute('data-status', 'active')
  })

  it('還沒設定：開關關著、Anthropic 選著、key 欄說要貼上、還沒填模型', async () => {
    render()
    renderApp('/settings/ai')

    expect(await screen.findByRole('heading', { level: 1, name: 'AI 設定' })).toBeVisible()
    expect(await screen.findByRole('checkbox', { name: '開啟 AI' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Anthropic Messages' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByLabelText('API key')).toHaveAttribute('placeholder', '貼上 key')
    expect(screen.getByLabelText('Base URL')).toHaveAttribute(
      'placeholder',
      'https://api.anthropic.com',
    )
    expect(screen.getByText('還沒填模型。')).toBeVisible()
    expect(screen.queryByRole('button', { name: '移除 key' })).not.toBeInTheDocument()
  })

  it('key 只寫不讀：存過的 key 不出現，欄位空著並說已設定', async () => {
    render({}, IN_USE)
    renderApp('/settings/ai')

    const key = await screen.findByLabelText('API key')
    expect(key).toHaveValue('')
    expect(key).toHaveAttribute('placeholder', '已設定，貼上新的就換掉')
    expect(screen.getByRole('button', { name: '移除 key' })).toBeVisible()
  })

  it('認得的模型說出價目與查證日期', async () => {
    render({}, IN_USE)
    renderApp('/settings/ai')

    expect(
      await screen.findByText('每百萬 token：輸入 $2 · 輸出 $10 · 快取讀 $0.10 · 快取寫 $2.5'),
    ).toBeVisible()
    expect(screen.getByText('2026-10-27 查證')).toBeVisible()
  })

  it('切換接口：換成那一種存著的值；認不得的模型價目寫未知，不當 0', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: 'OpenAI 相容' }))

    expect(screen.getByLabelText('Base URL')).toHaveValue('https://api.deepseek.com')
    expect(screen.getByLabelText('模型')).toHaveValue('some-local-model')
    expect(screen.getByText('價目未知：用量頁的費用會寫「未知」，不當 0。')).toBeVisible()
    expect(screen.getByText(/現在用的是 Anthropic Messages。/)).toBeVisible()
  })

  it('改了模型還沒存：價目不猜', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    const model = await screen.findByLabelText('模型')
    await user.clear(model)
    await user.type(model, 'claude-opus-5-5')

    expect(screen.getByText('存了之後顯示這個模型的價目。')).toBeVisible()
  })

  it('儲存：送出選中那一種與開關，key 欄空著送 null；存完欄位清空並說已儲存', async () => {
    const stub = render({ [SAVE]: { body: IN_USE } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('checkbox', { name: '開啟 AI' }))
    await user.type(screen.getByLabelText('API key'), ' sk-ant-new ')
    await user.type(screen.getByLabelText('模型'), 'claude-sonnet-5-5')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, SAVE)).toEqual({
      provider: 'anthropic',
      base_url: '',
      model: 'claude-sonnet-5-5',
      api_key: 'sk-ant-new',
      enabled: true,
      tavily_api_key: null,
    })
    expect(screen.getByLabelText('API key')).toHaveValue('')
    expect(screen.getByLabelText('API key')).toHaveAttribute(
      'placeholder',
      '已設定，貼上新的就換掉',
    )
  })

  it('key_missing：標在 key 欄下；改了 key 欄就收掉', async () => {
    render({ [SAVE]: refusal(422, 'key_missing') })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('checkbox', { name: '開啟 AI' }))
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('這個接口還沒有 key：貼上一把。')).toBeVisible()
    expect(screen.getByLabelText('API key')).toHaveAttribute('aria-invalid', 'true')
    await user.type(screen.getByLabelText('API key'), 'k')
    expect(screen.queryByText('這個接口還沒有 key：貼上一把。')).not.toBeInTheDocument()
  })

  it('base_url_invalid：標在 Base URL 欄下', async () => {
    render({
      [SAVE]: refusal(422, 'base_url_invalid', "'api.deepseek.com' is not an http(s) address"),
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('Base URL'), 'api.deepseek.com')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('這不是 http(s) 的完整網址。')).toBeVisible()
    expect(screen.getByLabelText('Base URL')).toHaveAttribute('aria-invalid', 'true')
  })

  it('測試連線：送表單上還沒存的值，成功說哪個模型回話', async () => {
    const stub = render({ [TEST]: { body: CONNECTED } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: 'OpenAI 相容' }))
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    expect(await screen.findByText('連上了')).toBeVisible()
    expect(screen.getByText('claude-sonnet-5-5-20261001')).toBeVisible()
    expect(sent(stub, TEST)).toEqual({
      provider: 'openai',
      base_url: 'https://api.deepseek.com',
      model: 'some-local-model',
      api_key: null,
    })
    expect(calls(stub, SAVE)).toBe(0)
  })

  it('測試失敗：人話與補法，服務的原文與狀態碼收進技術細節', async () => {
    const rejected: AiTest = {
      ok: false,
      failure: 'key_rejected',
      status: 401,
      detail: '{"error": {"message": "invalid x-api-key"}}',
      model: '',
    }
    render({ [TEST]: { body: rejected } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '測試連線' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('服務不接受這把 key。')
    expect(alert).toHaveTextContent('換一把，或確認這把 key 是給這個網址用的。')
    const details = screen.getByTestId('technical-details')
    expect(details).toHaveTextContent('HTTP 401 · key_rejected')
    expect(details).toHaveTextContent('invalid x-api-key')
  })

  it('移除現在用的那一把：警告說 AI 會一併關掉，確認之後開關跟著關', async () => {
    const forgotten: AiSettings = {
      ...IN_USE,
      enabled: false,
      anthropic: { ...IN_USE.anthropic, has_key: false },
    }
    const stub = render({ 'DELETE /api/settings/ai/keys/anthropic': { body: forgotten } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '移除 key' }))
    expect(screen.getByText(/這是現在用的接口，AI 會一併關掉/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: '移除' }))

    expect(await screen.findByText('已移除 key。')).toBeVisible()
    expect(calls(stub, 'DELETE /api/settings/ai/keys/anthropic')).toBe(1)
    expect(screen.getByRole('checkbox', { name: '開啟 AI' })).not.toBeChecked()
    expect(screen.getByLabelText('API key')).toHaveAttribute('placeholder', '貼上 key')
  })

  it('存完：欄位換成後端存下的樣子（Anthropic 的 /v1 拿掉了）', async () => {
    const stored: AiSettings = {
      ...UNSET,
      anthropic: { ...UNSET.anthropic, base_url: 'https://gw.example/anthropic' },
    }
    render({ [SAVE]: { body: stored } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('Base URL'), 'https://gw.example/anthropic/v1')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(screen.getByLabelText('Base URL')).toHaveValue('https://gw.example/anthropic')
  })

  it('移除跟開關無關的 key：剛勾、還沒存的開啟留著', async () => {
    const withTavily: AiSettings = { ...UNSET, has_tavily_key: true }
    render({ 'DELETE /api/settings/ai/keys/tavily': { body: UNSET } }, withTavily)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('checkbox', { name: '開啟 AI' }))
    await user.click(screen.getByRole('button', { name: '移除 Tavily key' }))
    await user.click(screen.getByRole('button', { name: '移除' }))

    expect(await screen.findByText('已移除 key。')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: '開啟 AI' })).toBeChecked()
  })

  it('Tavily key 只寫不讀，貼了跟著儲存送出', async () => {
    const stub = render({ [SAVE]: { body: { ...IN_USE, has_tavily_key: true } } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('Tavily API key'), 'tvly-1')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(sent(stub, SAVE)).toMatchObject({ tavily_api_key: 'tvly-1', api_key: null })
    expect(screen.getByLabelText('Tavily API key')).toHaveValue('')
    expect(screen.getByRole('button', { name: '移除 Tavily key' })).toBeVisible()
  })

  it('en：文案與價目', async () => {
    await i18next.changeLanguage('en')
    try {
      render({}, IN_USE)
      renderApp('/settings/ai')

      expect(await screen.findByRole('heading', { level: 1, name: 'AI settings' })).toBeVisible()
      expect(await screen.findByRole('checkbox', { name: 'Turn on AI' })).toBeChecked()
      expect(
        screen.getByText(
          'Per million tokens: input $2 · output $10 · cache read $0.10 · cache write $2.5',
        ),
      ).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiModels, AiSettings, AiTest } from '../api/ai'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const READ = 'GET /api/settings/ai'
const SAVE = 'PUT /api/settings/ai'
const TEST = 'POST /api/settings/ai/test'
const FETCH = 'POST /api/settings/ai/models'

/** 沒按「取得模型」之前那一支：本機價目表照表單上的網址查。 */
function suggestKey(provider: string, baseUrl: string) {
  return `GET /api/settings/ai/models?${new URLSearchParams({ provider, base_url: baseUrl })}`
}

function fromPrices(models: string[]): AiModels {
  return { models, source: 'prices', failure: null, status: null, detail: '' }
}

const SONNET_PRICE = {
  input: '2',
  output: '10',
  cache_read: '0.10',
  cache_write: '2.5',
  source: { table: 'genai_prices', version: '0.1.13', vendor: 'Anthropic', verified: null },
} as const

const SUGGESTED = ['claude-haiku-5-5', 'claude-sonnet-5-5']
const DEEPSEEK = 'https://api.deepseek.com'
const DEEPSEEK_SUGGESTED = ['deepseek-flash', 'deepseek-pro']

/** 本機價目表的建議：Anthropic 官方、OpenAI 官方與 DeepSeek 的網址各一份。 */
const SUGGESTIONS: StubRoutes = {
  [suggestKey('anthropic', '')]: { body: fromPrices(SUGGESTED) },
  [suggestKey('openai', '')]: { body: fromPrices(['gpt-5.5']) },
  [suggestKey('openai', DEEPSEEK)]: { body: fromPrices(DEEPSEEK_SUGGESTED) },
}

const UNSET: AiSettings = {
  enabled: false,
  provider: 'anthropic',
  anthropic: { base_url: '', model: '', has_key: false, price: null },
  openai: { base_url: '', model: '', has_key: false, price: null },
  has_tavily_key: false,
}

/** 兩種都填過、現在用 Anthropic 而且開著。 */
const IN_USE: AiSettings = {
  ...UNSET,
  enabled: true,
  anthropic: {
    base_url: '',
    model: 'claude-sonnet-5-5',
    has_key: true,
    price: SONNET_PRICE,
  },
  openai: {
    base_url: DEEPSEEK,
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
    ...SUGGESTIONS,
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

/** 模型欄 datalist 現在的建議。 */
function suggestions() {
  return [...document.querySelectorAll('datalist option')].map((o) => o.getAttribute('value'))
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

  it('查得到價的模型說出價目與價目來源（genai-prices 的版本與它認出的服務商）', async () => {
    render({}, IN_USE)
    renderApp('/settings/ai')

    expect(
      await screen.findByText('每百萬 token：輸入 $2 · 輸出 $10 · 快取讀 $0.10 · 快取寫 $2.5'),
    ).toBeVisible()
    expect(screen.getByText('價目來源：genai-prices 0.1.13（Anthropic）')).toBeVisible()
  })

  it('genai-prices 沒有、Berth 補位表有的模型：來源寫補位表與查證日期', async () => {
    render(
      {},
      {
        ...IN_USE,
        anthropic: {
          ...IN_USE.anthropic,
          price: {
            ...SONNET_PRICE,
            source: { table: 'berth', version: '', vendor: '', verified: '2026-10-28' },
          },
        },
      },
    )
    renderApp('/settings/ai')

    expect(await screen.findByText('價目來源：Berth 補位表（2026-10-28 查證）')).toBeVisible()
  })

  it('模型欄的建議是本機價目表照這個端點認得的模型；切換接口跟著換', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await screen.findByLabelText('模型')
    await waitFor(() => expect(suggestions()).toEqual(SUGGESTED))
    await user.click(screen.getByRole('button', { name: 'OpenAI 相容' }))
    await waitFor(() => expect(suggestions()).toEqual(DEEPSEEK_SUGGESTED))
  })

  it('填了 DeepSeek 的網址、還沒存：建議馬上換成 DeepSeek 的，沒有請求帶 key、也沒有問端點', async () => {
    const stub = render()
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: 'OpenAI 相容' }))
    await waitFor(() => expect(suggestions()).toEqual(['gpt-5.5']))
    await user.type(screen.getByLabelText('API key'), 'sk-typed-not-sent')
    await user.type(screen.getByLabelText('Base URL'), DEEPSEEK)

    await waitFor(() => expect(suggestions()).toEqual(DEEPSEEK_SUGGESTED))
    expect(calls(stub, FETCH)).toBe(0)
    const sentAnywhere = stub.mock.calls.filter(
      ([input, init]) =>
        String(input).includes('sk-typed-not-sent') ||
        String(init?.body ?? '').includes('sk-typed-not-sent'),
    )
    expect(sentAnywhere).toEqual([])
  })

  it('取得模型：送表單上的接口、網址與 key（不送模型名），建議換成端點列的', async () => {
    const stub = render({
      [FETCH]: {
        body: {
          models: ['deepseek-flash', 'deepseek-v4-pro'],
          source: 'endpoint',
          failure: null,
          status: null,
          detail: '',
        },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: 'OpenAI 相容' }))
    await user.type(screen.getByLabelText('Base URL'), DEEPSEEK)
    await user.type(screen.getByLabelText('API key'), 'sk-deepseek')
    await user.click(screen.getByRole('button', { name: '取得模型' }))

    expect(await screen.findByText('這個端點列了 2 個模型，放進模型欄的清單了。')).toBeVisible()
    expect(suggestions()).toEqual(['deepseek-flash', 'deepseek-v4-pro'])
    expect(sent(stub, FETCH)).toEqual({
      provider: 'openai',
      base_url: DEEPSEEK,
      api_key: 'sk-deepseek',
    })
  })

  it('問不到：說明原因、退回本機表，模型名照樣能打；改了 base URL 之後取得的清單不留著', async () => {
    render(
      {
        [FETCH]: {
          body: {
            models: ['claude-fallback-from-prices'],
            source: 'prices',
            failure: 'key_rejected',
            status: 401,
            detail: '{"error":{"message":"invalid x-api-key"}}',
          },
        },
      },
      IN_USE,
    )
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '取得模型' }))

    expect(await screen.findByText('服務不接受這把 key。')).toBeVisible()
    expect(screen.getByText(/模型欄改用本機價目表的建議/)).toBeVisible()
    expect(suggestions()).toEqual(['claude-fallback-from-prices'])
    const model = screen.getByLabelText('模型')
    await user.clear(model)
    await user.type(model, 'my-own-model')
    expect(model).toHaveValue('my-own-model')
    // 改模型名不收：清單就是拿來選的。
    expect(suggestions()).toEqual(['claude-fallback-from-prices'])

    await user.type(screen.getByLabelText('Base URL'), 'https://gw.example')

    expect(screen.queryByText('服務不接受這把 key。')).not.toBeInTheDocument()
    expect(suggestions()).not.toContain('claude-fallback-from-prices')
  })

  it('端點不提供模型清單（DeepSeek 的 Anthropic 接口回 404）：說的是這個，不是 key 被拒', async () => {
    render(
      {
        [FETCH]: {
          body: {
            models: ['deepseek-flash'],
            source: 'prices',
            failure: 'not_found',
            status: 404,
            detail: '',
          },
        },
      },
      IN_USE,
    )
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '取得模型' }))

    expect(
      await screen.findByText('這個端點不提供模型清單（也可能是 Base URL 的路徑不對）。'),
    ).toBeVisible()
    expect(screen.queryByText('服務不接受這把 key。')).not.toBeInTheDocument()
    expect(suggestions()).toEqual(['deepseek-flash'])
  })

  it('端點列出空的：退回本機表，說端點沒有列模型', async () => {
    render({ [FETCH]: { body: fromPrices(SUGGESTED) } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '取得模型' }))

    expect(await screen.findByText(/這個端點沒有列出模型/)).toBeVisible()
  })

  it('取得的清單在改了 key 之後也收掉', async () => {
    render({ [FETCH]: { body: { ...fromPrices(['from-endpoint']), source: 'endpoint' } } }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '取得模型' }))
    await waitFor(() => expect(suggestions()).toEqual(['from-endpoint']))
    await user.type(screen.getByLabelText('API key'), 'sk-another')

    await waitFor(() => expect(suggestions()).toEqual(SUGGESTED))
  })

  it('存著 key、改了網址就按取得模型：key 欄說存著的只送到原本的網址', async () => {
    render({ [FETCH]: refusal(422, 'key_missing') }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('Base URL'), 'https://evil.example')
    await user.click(screen.getByRole('button', { name: '取得模型' }))

    expect(
      await screen.findByText(
        '存著的 key 只送到存它的那個網址。要用這個網址，貼上它的 key，或先移除存著的那把。',
      ),
    ).toBeVisible()
  })

  it('切換接口：換成那一種存著的值；認不得的模型價目寫未知，不當 0', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: 'OpenAI 相容' }))

    expect(screen.getByLabelText('Base URL')).toHaveValue('https://api.deepseek.com')
    expect(screen.getByLabelText('模型')).toHaveValue('some-local-model')
    expect(
      screen.getByText('價目未知：這個端點查不到這個模型的價，用量頁的費用會寫「未知」，不當 0。'),
    ).toBeVisible()
    expect(screen.getByText(/現在用的是 Anthropic Messages。/)).toBeVisible()
  })

  it('改了模型還沒存：價目不猜', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    const model = await screen.findByLabelText('模型')
    await user.clear(model)
    await user.type(model, 'claude-opus-5-5')

    expect(screen.getByText('存了之後顯示這個端點與模型的價目。')).toBeVisible()
  })

  it('改了 base URL 還沒存：價目跟著端點走，也不猜', async () => {
    render({}, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    const baseUrl = await screen.findByLabelText('Base URL')
    await user.type(baseUrl, 'https://api.deepseek.com/anthropic')

    expect(screen.getByText('存了之後顯示這個端點與模型的價目。')).toBeVisible()
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

  it('存著 key、改了網址被拒：key 欄說存著的只送到原本的網址；改回網址就收掉', async () => {
    render({ [TEST]: refusal(422, 'key_missing') }, IN_USE)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    const elsewhere =
      '存著的 key 只送到存它的那個網址。要用這個網址，貼上它的 key，或先移除存著的那把。'
    expect(await screen.findByLabelText('API key')).toHaveAccessibleDescription(
      expect.stringContaining('只送到存它的那個 base URL'),
    )
    await user.type(screen.getByLabelText('Base URL'), 'https://gw.example')
    await user.click(screen.getByRole('button', { name: '測試連線' }))

    expect(await screen.findByText(elsewhere)).toBeVisible()
    expect(screen.getByLabelText('API key')).toHaveAttribute('aria-invalid', 'true')
    await user.clear(screen.getByLabelText('Base URL'))
    expect(screen.queryByText(elsewhere)).not.toBeInTheDocument()
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

  it('OpenAI 相容而沒有 Tavily key：建議填，Anthropic 或已有 key 時不提', async () => {
    const TIP = /整部系列與評價需要網路搜尋/
    render({}, { ...IN_USE, provider: 'openai' })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    expect(await screen.findByText(TIP)).toBeVisible()
    // 貼了一把（還沒存）就不再提
    await user.type(screen.getByLabelText('Tavily API key'), 'tvly-1')
    expect(screen.queryByText(TIP)).toBeNull()
    await user.clear(screen.getByLabelText('Tavily API key'))
    // Anthropic 有自己的伺服器端搜尋
    await user.click(screen.getByRole('button', { name: 'Anthropic Messages' }))
    expect(screen.queryByText(TIP)).toBeNull()
  })

  it('OpenAI 相容、已存 Tavily key：不提', async () => {
    render({}, { ...IN_USE, provider: 'openai', has_tavily_key: true })
    renderApp('/settings/ai')

    expect(await screen.findByLabelText('Tavily API key')).toBeVisible()
    expect(screen.queryByText(/整部系列與評價需要網路搜尋/)).toBeNull()
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
      expect(screen.getByText('Price source: genai-prices 0.1.13 (Anthropic)')).toBeVisible()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

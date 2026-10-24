import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiSettings, AiTest } from '../api/ai'
import { HEALTHY, stubApi, type StubRoutes } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const READ = 'GET /api/settings/ai'
const SAVE = 'PUT /api/settings/ai'
const TEST = 'POST /api/settings/ai/test'.replace('这', '這').replace('側', '側')
const CHAT_ONLY_TEXT = '這個模型只能聊天，側面板不能替你訂閱、搜尋或下載。'

const READY: AiSettings = {
  format: 'anthropic',
  base_url: '',
  api_key_present: true,
  model: '',
  official_models: { anthropic: 'claude-opus-5-5', openai: null },
  ready: true,
  tool_test: null,
}

const UNSUPPORTED: AiSettings = {
  ...READY,
  tool_test: {
    supported: false,
    gap: 'tools_ignored',
    detail: 'no tool_use block',
    tested_at: '2026-10-24T08:00:00Z',
  },
}

const NO_USAGE = {
  input_tokens: null,
  output_tokens: null,
  cache_write_tokens: null,
  cache_read_tokens: null,
}

const CONNECTED: AiTest = {
  failure: null,
  detail: '',
  retry_after: null,
  reply: 'hello there',
  calls: [
    {
      step: 'hello',
      usage: { ...NO_USAGE, input_tokens: 1234, output_tokens: 5, cache_write_tokens: 0 },
    },
  ],
  tools: {
    supported: true,
    gap: null,
    detail: '',
    tested_at: '2026-10-24T08:00:00Z',
  },
  tools_failure: null,
  tools_detail: '',
}

function render(settings: AiSettings = READY, routes: StubRoutes = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [READ]: { body: settings },
    ...routes,
  })
}

function bodyOf(stub: ReturnType<typeof stubApi>, key: string): unknown {
  const call = stub.mock.calls.find(
    ([input, init]) => `${init?.method ?? 'GET'} ${String(input)}` === key,
  )
  return JSON.parse(String(call?.[1]?.body))
}

function methodsCalled(stub: ReturnType<typeof stubApi>): string[] {
  return stub.mock.calls.map(([input, init]) => `${init?.method ?? 'GET'} ${String(input)}`)
}

describe('設定 → AI', () => {
  it('分頁列倒數第二格是 AI（最後是用量），當前頁', async () => {
    render()
    renderApp('/settings/ai')

    const tabs = within(await screen.findByRole('navigation', { name: '設定' }))
    expect(tabs.getAllByRole('link').at(-2)).toHaveTextContent('AI')
    expect(tabs.getByRole('link', { name: 'AI' })).toHaveAttribute('data-status', 'active')
  })

  it('存著的測試結論是只能聊天：說側面板不能替你做事', async () => {
    render(UNSUPPORTED)
    renderApp('/settings/ai')

    expect(await screen.findByText(CHAT_ONLY_TEXT)).toBeVisible()
    expect(screen.getByText('端點忽略了工具，模型只回了文字。')).toBeVisible()
  })

  it('改了模型還沒存：說儲存後要重新測試，不再顯示舊的結論', async () => {
    render(UNSUPPORTED)
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await screen.findByText(CHAT_ONLY_TEXT)
    await user.type(screen.getByLabelText('模型'), 'claude-x')

    expect(screen.getByText('改了格式、base URL 或模型：儲存後要重新測試。')).toBeVisible()
    expect(screen.queryByText(CHAT_ONLY_TEXT)).not.toBeInTheDocument()
  })

  it('沒輸入 key 就儲存：api_key 是 null，key 原文不在畫面上', async () => {
    const stub = render(READY, { [SAVE]: { body: { ...READY, model: 'claude-x' } } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('模型'), 'claude-x')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(bodyOf(stub, SAVE)).toEqual({
      format: 'anthropic',
      base_url: '',
      model: 'claude-x',
      api_key: null,
    })
    expect(screen.getByLabelText('API key')).toHaveValue('')
    expect(screen.getByLabelText('API key')).toHaveAttribute('placeholder', '已設定，留空不改')
  })

  it('輸入 key 才帶 key，存完欄位清空', async () => {
    const stub = render(READY, { [SAVE]: { body: READY } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('API key'), 'sk-secret')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(bodyOf(stub, SAVE)).toMatchObject({ api_key: 'sk-secret' })
    expect(screen.getByLabelText('API key')).toHaveValue('')
    expect(screen.queryByText('sk-secret')).not.toBeInTheDocument()
  })

  it('base URL 不合格：錯誤掛在欄位上', async () => {
    render(READY, {
      [SAVE]: {
        status: 422,
        body: { detail: { reason: 'base_url_invalid', detail: 'not a url' } },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('Base URL'), 'ftp://x')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    const field = await screen.findByLabelText('Base URL')
    await waitFor(() => expect(field).toBeInvalid())
    expect(screen.getByText(/http:\/\/ 或 https:\/\/ 開頭的完整網址/)).toBeVisible()
  })

  it('儲存並測試：先 PUT 再 POST；失敗是 auth_failed 就說那一句', async () => {
    const failed: AiTest = {
      ...CONNECTED,
      failure: 'auth_failed',
      detail: '401 invalid x-api-key',
      reply: '',
      calls: [],
      tools: null,
    }
    const stub = render(READY, {
      [SAVE]: { body: { ...READY, model: 'claude-x' } },
      [TEST]: { body: failed },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.type(await screen.findByLabelText('模型'), 'claude-x')
    await user.click(screen.getByRole('button', { name: '儲存並測試' }))

    expect(await screen.findByText('端點不接受這把 key。')).toBeVisible()
    expect(screen.getByText('確認 key 沒有過期、貼的是這個端點的 key。')).toBeVisible()
    const calls = methodsCalled(stub).filter((call) => call !== 'GET /api/health')
    expect(calls.indexOf(SAVE)).toBeGreaterThan(-1)
    expect(calls.indexOf(TEST)).toBeGreaterThan(calls.indexOf(SAVE))
  })

  it('成功的結果：連得上、模型的話、tokens 表；不知道的格子不是 0', async () => {
    render(READY, { [TEST]: { body: CONNECTED } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '儲存並測試' }))

    expect(await screen.findByText('連得上')).toBeVisible()
    expect(screen.getByText('模型回的話：hello there')).toBeVisible()
    expect(screen.getByText('支援工具呼叫。')).toBeVisible()
    const row = screen.getByRole('row', { name: /連線/ })
    const cells = within(row).getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['1,234', '5', '0', '不知道'])
  })

  it('測試沒過：狀態那一格不只說設定好了，改了欄位之後那句收起', async () => {
    render(READY, {
      [TEST]: {
        body: { ...CONNECTED, failure: 'auth_failed', reply: '', calls: [], tools: null },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '儲存並測試' }))

    const note = '但剛才的測試沒過，見下方的「測試」。'
    expect(await screen.findByText(note)).toBeVisible()
    await user.type(screen.getByLabelText('模型'), 'claude-x')
    expect(screen.queryByText(note)).toBeNull()
  })

  it('測出只能聊天：與狀態那一格同一個意思（等你決定），不是紅色的失敗', async () => {
    render(READY, {
      [TEST]: { body: { ...CONNECTED, tools: UNSUPPORTED.tool_test } },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '儲存並測試' }))

    expect(await screen.findByText('只能聊天。')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByText('但剛才的測試沒過，見下方的「測試」。')).toBeNull()
  })

  it('沒測到工具結論：說稍後再測，並說 failure 的句子', async () => {
    render(READY, {
      [TEST]: {
        body: {
          ...CONNECTED,
          tools: null,
          tools_failure: 'provider_down',
          tools_detail: '529',
        },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '儲存並測試' }))

    expect(await screen.findByText('這次沒測成工具呼叫，稍後再測。')).toBeVisible()
    expect(screen.getByText('provider 暫時有問題。')).toBeVisible()
  })

  it('讀模型清單：塞進 datalist 並說讀到幾個', async () => {
    render(READY, {
      'GET /api/settings/ai/models': {
        body: { models: ['m-a', 'm-b'], failure: null, detail: '' },
      },
    })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    await user.click(await screen.findByRole('button', { name: '從端點讀取模型清單' }))

    expect(await screen.findByText('讀到 2 個模型，從欄位的建議裡挑。')).toBeVisible()
    const list = document.getElementById(screen.getByLabelText('模型').getAttribute('list')!)
    expect([...list!.querySelectorAll('option')].map((option) => option.value)).toEqual([
      'm-a',
      'm-b',
    ])
  })

  it('切到 OpenAI 相容：base URL 照它的慣例說明；官方端點沒有預設模型，要先填', async () => {
    const saved: AiSettings = {
      ...READY,
      format: 'openai',
      model: 'gpt-x',
      ready: true,
    }
    const stub = render(READY, { [SAVE]: { body: saved } })
    const user = userEvent.setup()
    renderApp('/settings/ai')

    const model = await screen.findByLabelText('模型')
    expect(model).toHaveAttribute('placeholder', 'claude-opus-5-5')
    await user.selectOptions(screen.getByLabelText('格式'), 'OpenAI 相容（Chat Completions）')

    expect(screen.getByLabelText('Base URL')).toHaveAttribute(
      'placeholder',
      'https://api.openai.com/v1',
    )
    expect(screen.getByText(/含 \/v1，例如 https:\/\/openrouter\.ai\/api\/v1/)).toBeVisible()
    expect(model).toHaveAttribute('placeholder', '')
    expect(screen.getByText('這個端點需要模型：先選或填一個。')).toBeVisible()

    await user.type(model, 'gpt-x')
    expect(screen.queryByText('這個端點需要模型：先選或填一個。')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '儲存' }))

    expect(await screen.findByText('已儲存。')).toBeVisible()
    expect(bodyOf(stub, SAVE)).toMatchObject({ format: 'openai', model: 'gpt-x' })
  })
})

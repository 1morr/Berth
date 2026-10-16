import { screen } from '@testing-library/react'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BERTHS } from '../components/berths'
import { HEALTHY, stubApi } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18next.changeLanguage('zh-Hant')
})

/**
 * 設定頁的每一個分頁底部說得出跑的是哪一版（票 106）：使用者原本只能自己打 `/api/health`。
 * 版本讀的是路由守衛已經在讀的那一份 `GET /api/health`，不另開端點。
 */
describe('設定頁的 Berth 版本', () => {
  const pages = BERTHS.map((berth) => berth.settings)

  it.each(
    pages.flatMap((path) => [
      ['zh-Hant', path],
      ['en', path],
    ]),
  )('%s：%s 看得到 Berth 的版本', async (language, path) => {
    await i18next.changeLanguage(language)
    stubApi({
      'GET /api/health': { body: { ...HEALTHY, version: '0.2.7' } },
      'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
      'GET /api/routes': { body: [] },
    })
    renderApp(path)

    expect(await screen.findByText('Berth 0.2.7')).toBeVisible()
  })
})

import { render, screen } from '@testing-library/react'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import { Timestamp } from './Timestamp'

const NOW = Date.parse('2026-10-08T12:00:00Z')

afterEach(async () => {
  vi.useRealTimers()
  await i18next.changeLanguage('zh-Hant')
})

/**
 * 瀏覽器的時鐘比伺服器慢兩秒時，「最後成功」原本說成「2 秒後」（M4 票 55 實測，記在票 68）。已經發生的
 * 時間（`past`）落在未來就說成現在；預約的時間照說未來。
 */
describe.each([
  ['zh-Hant', '現在', '2 秒後'],
  ['en', 'now', 'in 2 seconds'],
])('%s', (language, now, later) => {
  it('已經發生的時間落在未來時說現在', async () => {
    await i18next.changeLanguage(language)
    vi.useFakeTimers({ now: NOW, toFake: ['Date'] })

    render(<Timestamp at={new Date(NOW + 2000).toISOString()} past />)

    expect(screen.getByRole('time')).toHaveTextContent(now)
  })

  it('預約的時間照說未來', async () => {
    await i18next.changeLanguage(language)
    vi.useFakeTimers({ now: NOW, toFake: ['Date'] })

    render(<Timestamp at={new Date(NOW + 2000).toISOString()} />)

    expect(screen.getByRole('time')).toHaveTextContent(later)
  })
})

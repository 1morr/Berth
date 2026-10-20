import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'

import { resources } from '../i18n/resources'
import { routeView } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { RouteDelete } from './RouteDelete'

const IN_USE = { jobs: 1, ledger_entries: 0, rss_feeds: 0, rss_series: 0, in_use: true }

/** 刪除元件本身的契約（票 14a）。畫面上的流程在 `RouteSettingsPage.test.tsx` 與 `SetupPage.routes.test.tsx`。 */
describe('RouteDelete', () => {
  it('被引用而且還啟用著：給了 onDisable 才有停用鈕', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView()}
        usage={IN_USE}
        onDelete={async () => {}}
        onDisable={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: '停用這條 Route' })).toBeInTheDocument()
  })

  it('沒給 onDisable（精靈）就只說刪不得，不給停用鈕——停用是設定頁的事', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView()}
        usage={IN_USE}
        onDelete={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByText(/刪不得/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '停用這條 Route' })).not.toBeInTheDocument()
  })

  it('已經停用的就不叫人去停用', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView({ enabled: false })}
        usage={IN_USE}
        onDelete={async () => {}}
        onDisable={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByText(/已經停用/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '停用這條 Route' })).not.toBeInTheDocument()
  })

  // 票 115：只有 RSS 綁著的 Route，下載與檔案都是 0，說明要說出 RSS 的數字，不然看不出為什麼刪不得。
  it.each([
    ['zh-Hant', '還有 0 筆下載、0 個入庫檔案、1 個 RSS Feed、2 個 RSS Series'],
    ['en', '0 downloads, 0 imported files, 1 RSS feed, and 2 RSS Series point at this route'],
  ])('%s：RSS 綁著時說出 Feed 與 Series 的數量', async (language, said) => {
    await i18next.changeLanguage(language)
    try {
      renderWithProviders(
        <RouteDelete
          route={routeView()}
          usage={{ jobs: 0, ledger_entries: 0, rss_feeds: 1, rss_series: 2, in_use: true }}
          onDelete={async () => {}}
          onChanged={() => {}}
        />,
      )

      expect(screen.getByText(new RegExp(said))).toBeInTheDocument()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  it('沒有 RSS 綁著就不說 RSS', () => {
    renderWithProviders(
      <RouteDelete
        route={routeView()}
        usage={IN_USE}
        onDelete={async () => {}}
        onChanged={() => {}}
      />,
    )

    expect(screen.getByText(/刪不得/)).toHaveTextContent('還有 1 筆下載、0 個入庫檔案')
    expect(screen.getByText(/刪不得/)).not.toHaveTextContent('RSS')
  })

  it.each([
    ['zh-Hant', '刪的那一刻發現這條 Route 還有 0 筆下載、0 個入庫檔案、1 個 RSS Feed'],
    ['en', 'When it came to deleting, 0 downloads, 0 imported files, and 1 RSS feed turned out'],
  ])('%s：409 帶的 RSS 數字也照說', async (language, said) => {
    await i18next.changeLanguage(language)
    try {
      const body = {
        reason: 'route_in_use',
        detail: 'jobs=0 · ledger_entries=0 · rss_feeds=1 · rss_series=0',
        jobs: 0,
        ledger_entries: 0,
        rss_feeds: 1,
        rss_series: 0,
      }
      renderWithProviders(
        <RouteDelete
          route={routeView()}
          onDelete={async () => {
            throw new ApiError(409, 'route_in_use', body)
          }}
          onChanged={() => {}}
        />,
      )
      await userEvent.click(
        screen.getByRole('button', { name: i18next.t('routeSettings.delete.label') }),
      )
      await userEvent.click(
        screen.getByRole('button', { name: i18next.t('routeSettings.delete.confirm') }),
      )

      expect(await screen.findByText(new RegExp(said))).toBeInTheDocument()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })

  // 票 120：usage 結尾是拉丁字（「RSS Feed」）時，後面直接接中文字會少一個空格。刪除那一組裡帶
  // {{usage}} 的每一句都讓它接標點；之後新加的句子自動被掃到。
  const usageCopy: Array<[string, string]> = Object.entries(
    resources['zh-Hant'].translation.routeSettings.delete,
  ).filter(([, text]) => text.includes('{{usage}}'))

  it('掃得到帶 {{usage}} 的句子', () => {
    expect(usageCopy.map(([key]) => key)).toEqual(
      expect.arrayContaining(['inUse', 'inUseDisabled', 'refused']),
    )
  })

  it.each(usageCopy)('zh-Hant 的 %s：{{usage}} 後面接標點', (_key, text) => {
    const said = text.replace('{{usage}}', '1 個 RSS Feed')

    expect(said).toMatch(/1 個 RSS Feed[，。]/)
    expect(said).not.toMatch(/Feed指/)
  })
})

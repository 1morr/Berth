import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubApi } from '../test/fetch'
import { renderInRoute } from '../test/render'
import { ALL_BUNDLED, RECOMMENDED, indexerSetup, setupStatus, site } from '../test/fixtures'
import { SetupPage } from './SetupPage'

/**
 * 頁 4 套件內的版面（M4 票 119）：加站與介面登入是兩件必填，桌機時登入搬到剖面底下，兩欄才不會一欄
 * 一屏半、另一欄三分之一屏。窄版只有一欄，登入照舊接在加站後面、導覽之前（導覽是這一頁最後一件事）。
 */

afterEach(() => {
  vi.unstubAllGlobals()
})

const AT_INDEXER = setupStatus({ current_step: 4, owner: 'skipper', services: ALL_BUNDLED })

/** jsdom 沒有 `matchMedia`：替它給一個固定的答案（`lg` 是 64rem）。 */
function screenWidth(wide: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: wide && query.includes('64rem'),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
}

async function page4(indexers = indexerSetup()) {
  stubApi({
    'GET /api/setup/status': { body: AT_INDEXER },
    'GET /api/setup/indexers': { body: indexers },
  })
  renderInRoute(<SetupPage />)
  const login = await screen.findByTestId('prowlarr-login')
  const work = screen
    .getByRole('heading', { name: 'Prowlarr', level: 2 })
    .closest('[data-frame-column]')
  const cutaway = screen
    .getByRole('heading', { name: 'Prowlarr', level: 3 })
    .closest('[data-frame-column]')
  return { login, work, cutaway }
}

describe('頁 4 套件內的介面登入放在哪一欄', () => {
  it('桌機：在剖面那一欄、剖面之後', async () => {
    screenWidth(true)

    const { login, work, cutaway } = await page4()

    expect(cutaway).toContainElement(login)
    expect(work).not.toContainElement(login)
  })

  it('窄版：在工作面、加站之後、導覽之前', async () => {
    screenWidth(false)

    const { login, work } = await page4()

    expect(work).toContainElement(login)
    const sites = screen.getByTestId('recommended-sites')
    const nav = screen.getByRole('navigation', { name: '泊位導覽' })
    expect(sites.compareDocumentPosition(login) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(login.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('沒有 matchMedia 的環境當窄版', async () => {
    vi.stubGlobal('matchMedia', undefined)

    const { login, work } = await page4()

    expect(work).toContainElement(login)
  })
})

/**
 * 先後（M4 票 119 的 critique）：還沒加站時「測試推薦站」是這一頁唯一的調度黃，登入的送出鍵是次要的；
 * 兩顆黃鍵左右並排時看不出先做哪一件。加了站之後登入才是「現在需要你」的那一件。
 */
describe('頁 4 套件內：一屏只有一顆調度黃', () => {
  const ASSIGNED = 'bg-assigned'

  it('還沒加站：登入的送出鍵不是主鍵', async () => {
    screenWidth(true)

    await page4()

    expect(screen.getByRole('button', { name: '測試推薦站，加入通過的' })).toHaveClass(ASSIGNED)
    expect(screen.getByRole('button', { name: '設定介面登入' })).not.toHaveClass(ASSIGNED)
  })

  it('加了站：登入的送出鍵是主鍵', async () => {
    screenWidth(true)

    await page4(indexerSetup({ sites: [site(RECOMMENDED[0], 1)] }))

    expect(screen.getByRole('button', { name: '設定介面登入' })).toHaveClass(ASSIGNED)
  })
})

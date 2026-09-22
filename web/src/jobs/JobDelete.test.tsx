import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { stubApi, type StubRoute } from '../test/fetch'
import { renderWithProviders } from '../test/render'
import { JobDelete } from './JobDelete'

const HASH = 'a'.repeat(40)

/** 一份估算。預設是「五個鏈接、六個來源、全部刪掉可空出 1.4 GB」。 */
function estimate(overrides: Record<string, number> = {}) {
  return {
    links: 5,
    links_missing: 0,
    link_bytes: 1_500_000_000,
    sources: 6,
    sources_missing: 0,
    source_bytes: 1_500_000_000,
    reclaimable: 1_500_000_000,
    held: 0,
    ...overrides,
  }
}

/** 一次刪除的結果。 */
function outcome(overrides: Record<string, number | boolean> = {}) {
  return { links: 5, sources: 0, torrent: false, purged: false, freed: 0, ...overrides }
}

function mount(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  const stub = stubApi({
    [`GET /api/jobs/${HASH}/deletion`]: { body: estimate() },
    [`DELETE /api/jobs/${HASH}?unlink=false&remove_torrent=false&delete_files=false&purge=false`]: {
      body: outcome({ links: 0 }),
    },
    ...routes,
  })
  renderWithProviders(<JobDelete hash={HASH} />)
  return stub
}

/** 打開對話框。**估算在這一刻才問**（展開前不該碰磁碟）。 */
async function open() {
  await userEvent.click(screen.getByRole('button', { name: '刪除' }))
}

function tick(name: string | RegExp) {
  return userEvent.click(screen.getByRole('checkbox', { name }))
}

/** 這一次送出去的 `DELETE` 網址。四個旗標是 query 參數。 */
function deleted(stub: ReturnType<typeof stubApi>): string {
  const call = stub.mock.calls.find(([, init]) => init?.method === 'DELETE')
  expect(call).toBeDefined()
  return String(call?.[0])
}

describe('JobDelete', () => {
  it('展開之前不問估算——它會去摸磁碟上的每一個檔案', () => {
    const stub = mount()

    expect(stub.mock.calls).toHaveLength(0)
  })

  it('四個旗標預設全不勾', async () => {
    mount()

    await open()

    for (const box of screen.getAllByRole('checkbox')) expect(box).not.toBeChecked()
  })

  it('估算在算的時候畫面說得出自己正在做什麼', async () => {
    // 估算**永遠不回**：使用者看到的就是「正在算」那一刻。逐一 `stat` 幾十個檔案真的會
    // 花好幾秒（brief §9.2），而那幾秒畫面不能是一片空白。
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => new Promise<Response>(() => {})),
    )
    renderWithProviders(<JobDelete hash={HASH} />)

    await open()

    expect(screen.getByText('正在逐一量測這幾個檔案…')).toBeInTheDocument()
  })

  it('算完之後說得出兩邊各有幾個', async () => {
    mount()

    await open()

    expect(await screen.findByText(/媒體庫 5 個鏈接 · 下載目錄 6 個檔案/)).toBeInTheDocument()
  })

  it('只勾移除鏈接時說的是「不會空出空間」', async () => {
    // 硬鏈接是同一份資料的兩個名字，下載目錄那一份還在就等於什麼都沒釋放（brief §9.2）。
    mount()
    await open()
    await screen.findByText(/媒體庫 5 個鏈接/)

    await tick('移除媒體庫裡的硬鏈接')

    expect(screen.getByText(/這樣刪不會空出空間/)).toBeInTheDocument()
  })

  it('兩邊都勾才說得出會空出多少', async () => {
    mount()
    await open()
    await screen.findByText(/媒體庫 5 個鏈接/)

    await tick('移除媒體庫裡的硬鏈接')
    await tick('從 qBittorrent 移除這個 torrent')
    await tick('刪除下載目錄裡的檔案')

    expect(screen.getByText(/這樣刪會空出 1\.4 GB/)).toBeInTheDocument()
  })

  it('沒勾移除 torrent 時刪檔那一格是鎖住的，而且說得出怎麼解鎖', async () => {
    // 後端那一條是 422（`delete_files_requires_remove_torrent`），這裡是同一條規則的畫面版。
    mount()

    await open()

    expect(screen.getByRole('checkbox', { name: '刪除下載目錄裡的檔案' })).toBeDisabled()
    expect(screen.getByText('先勾上面那一格才選得了。')).toBeInTheDocument()
  })

  it('取消移除 torrent 會把刪檔那一格一起收掉', async () => {
    // 留著一個送出去一定被擋下來的勾，等於讓使用者按一顆註定失敗的按鈕。
    mount()
    await open()
    await tick('從 qBittorrent 移除這個 torrent')
    await tick('刪除下載目錄裡的檔案')

    await tick('從 qBittorrent 移除這個 torrent')

    expect(screen.getByRole('checkbox', { name: '刪除下載目錄裡的檔案' })).not.toBeChecked()
  })

  it('勾了哪幾格就送哪幾個旗標', async () => {
    const stub = mount({
      [`DELETE /api/jobs/${HASH}?unlink=true&remove_torrent=false&delete_files=false&purge=true`]: {
        body: outcome(),
      },
    })
    await open()
    await tick('移除媒體庫裡的硬鏈接')
    await tick('清除帳本與這一筆的紀錄')

    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    await waitFor(() =>
      expect(deleted(stub)).toBe(
        `/api/jobs/${HASH}?unlink=true&remove_torrent=false&delete_files=false&purge=true`,
      ),
    )
  })

  it('刪完說的是真的做掉了什麼，不是勾選的回聲', async () => {
    // 勾了「移除鏈接」而那幾個檔案早就被人刪掉時，後端回的是 0——畫面照它說。
    mount({
      [`DELETE /api/jobs/${HASH}?unlink=true&remove_torrent=false&delete_files=false&purge=false`]:
        { body: outcome({ links: 0, sources: 0, freed: 0 }) },
    })
    await open()
    await tick('移除媒體庫裡的硬鏈接')

    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    expect(
      await screen.findByText('已移除 0 個鏈接、刪掉 0 個檔案，沒有空出空間。'),
    ).toBeInTheDocument()
  })

  it('被拒絕時說的是那個封閉集合的理由，不是一句通用的話', async () => {
    mount({
      [`DELETE /api/jobs/${HASH}?unlink=false&remove_torrent=false&delete_files=false&purge=false`]:
        {
          status: 502,
          body: { detail: { reason: 'client_unreachable', detail: 'connection refused' } },
        },
    })
    await open()

    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/連不上 qBittorrent/)
  })

  it('算不出來時仍然刪得下去——估算是參考，不是刪除的前提', async () => {
    mount({ [`GET /api/jobs/${HASH}/deletion`]: { status: 503, body: { detail: 'down' } } })

    await open()

    expect(await screen.findByText(/算不出可以空出多少/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '確認刪除' })).toBeEnabled()
  })

  it('取消把勾選收回預設——下一次打開不會帶著上一次的決定', async () => {
    mount()
    await open()
    await tick('移除媒體庫裡的硬鏈接')

    await userEvent.click(screen.getByRole('button', { name: '取消' }))
    await open()

    for (const box of screen.getAllByRole('checkbox')) expect(box).not.toBeChecked()
  })
})

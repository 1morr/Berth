import { focusManager } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AuditReviewRow, DuplicateReviewRow, ReviewQueue } from '../api/review'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const QUEUE = 'GET /api/review'
const TARGET =
  '/data/library/anime/SPY x FAMILY (2022) [tmdbid-120089]/Season 02/SPY x FAMILY (2022) - S02E01.mkv'
const SOURCE = '/data/torrent/complete/anime/[ANi] SPY×FAMILY - 26.mkv'
const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'
const OTHER = 'aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00'

function audit(overrides: Partial<AuditReviewRow> = {}): AuditReviewRow {
  return {
    kind: 'audit',
    ref: 7,
    reason: { code: 'medium_auto_imported', params: {} },
    actions: ['confirm', 'undo'],
    at: '2026-09-22T04:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: HASH,
    job_name: '[ANi] SPY×FAMILY - 26 [1080P][WEB-DL][AAC AVC][CHT]',
    path: TARGET,
    source_path: SOURCE,
    season: 2,
    episode_start: 1,
    episode_end: null,
    reasons: [{ code: 'absolute_cumulative', params: { number: 26, episode: 'S02E01' } }],
    ...overrides,
  }
}

function duplicate(): DuplicateReviewRow {
  return {
    kind: 'duplicate',
    ref: 40,
    reason: { code: 'same_version', params: {} },
    actions: ['replace', 'keep_both', 'skip'],
    at: '2026-09-22T05:00:00Z',
    media_id: 'tv:120089',
    title: 'SPY×FAMILY 間諜家家酒',
    title_en: 'SPY x FAMILY',
    job_hash: OTHER,
    job_name: '[Group] SPY×FAMILY S01E03',
    path: '/data/torrent/complete/anime/[Group] SPY×FAMILY S01E03.mkv',
    season: 1,
    episode_start: 3,
    episode_end: null,
    known_path: '/data/library/anime/SPY x FAMILY/Season 01/SPY x FAMILY - S01E03.mkv',
    known_season: 1,
    known_episode_start: 3,
    known_episode_end: null,
  }
}

function queue(rows: ReviewQueue['rows'], total = rows.length, issuesOpen = 0): StubRoute {
  return { body: { rows, total, queue_total: total, issues_open: issuesOpen } }
}

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': { body: { name: 'skipper', role: 'admin' } },
    [QUEUE]: queue([]),
    ...routes,
  })
}

/** `POST /api/review/audit/confirm` 送出去的那幾個 id；還沒送是 `null`。 */
function sentIds(stub: ReturnType<typeof render>) {
  const call = stub.mock.calls.find(([url]) => url === '/api/review/audit/confirm')
  return call ? (JSON.parse(String(call[1]?.body)) as { ledger_ids: number[] }).ledger_ids : null
}

describe('審核佇列', () => {
  it('audit 那一列說得出是哪一集、為什麼在這裡、按得了什麼', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')

    const row = await screen.findByRole('article')

    expect(within(row).getByRole('heading')).toHaveTextContent('SPY×FAMILY 間諜家家酒 S02E01')
    // 理由是 code，句子是前端翻的；收起時就說出主要原因，不必展開（M3 票 05）。
    expect(within(row).getByText(/信心 medium：集號是換算的（各季集數累加）/)).toBeInTheDocument()
    expect(within(row).getByText('待確認')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '確認' })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: '撤銷' })).toBeInTheDocument()
  })

  it('展開之後看得到兩條路徑與解析器的理由（翻譯過的句子）', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByText(TARGET)).toBeInTheDocument()
    expect(within(row).getByText(SOURCE)).toBeInTheDocument()
    expect(within(row).getByText('各季集數依序累加，#26 落在 S02E01')).toBeInTheDocument()
  })

  it('所屬下載那一格連到它的詳情頁，不是整份下載列表（M2 票 12）', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByText('展開'))

    expect(within(row).getByRole('link', { name: /SPY×FAMILY - 26/ })).toHaveAttribute(
      'href',
      `/jobs/${HASH}`,
    )
  })

  it('audit 與重複版本在同一段，空的段不畫', async () => {
    render({ [QUEUE]: queue([audit(), duplicate()]) })
    renderApp('/review')

    await screen.findAllByRole('article')
    const headings = screen.getAllByRole('heading', { level: 2 }).map((node) => node.textContent)

    expect(headings).toEqual(['已入庫，等你看一眼2'])
    expect(screen.queryByText('要你決定')).not.toBeInTheDocument()
  })

  it('按確認之後那一列消失，並對看不見畫面的人說一聲', async () => {
    let rows: ReviewQueue['rows'] = [audit()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/confirm': () => {
        rows = []
        return { status: 204, body: null }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '確認' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(screen.getByText('沒有事在等你。')).toBeInTheDocument()
    expect(screen.getByText('已確認，這一列從佇列上收掉了。')).toBeInTheDocument()
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/confirm')).toBe(true)
  })

  // M2 票 16 的 critique：按下去的那一顆跟著整列消失，焦點掉回 `body`——鍵盤使用者清一件佇列就要
  // 從頁首重新 Tab 一次。焦點改落在接替那一格的那一列；清空了就落在頁標題。
  it('按完那一列消失之後，焦點落在接著的那一列，清空了落在頁標題', async () => {
    // 兩筆不同的下載：同一筆的會收成一組（下面「同一個 Job」那幾條）。
    let rows: ReviewQueue['rows'] = [audit(), audit({ ref: 8, episode_start: 2, job_hash: OTHER })]
    render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/confirm': () => {
        rows = rows.filter((row) => row.ref !== 7)
        return { status: 204, body: null }
      },
      'POST /api/review/audit/8/confirm': () => {
        rows = []
        return { status: 204, body: null }
      },
    })
    renderApp('/review')
    const [first] = await screen.findAllByRole('article')

    within(first).getByRole('button', { name: '確認' }).focus()
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1))
    const [next] = screen.getAllByRole('article')
    await waitFor(() => expect(next).toHaveFocus())
    // 焦點落到那一列時念得出是哪一件。
    expect(next).toHaveAccessibleName('SPY×FAMILY 間諜家家酒 S02E02')

    within(next).getByRole('button', { name: '確認' }).focus()
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveFocus())
  })

  it('撤銷要就地確認一次，說出後果之後才送出', async () => {
    let rows: ReviewQueue['rows'] = [audit()]
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/undo': () => {
        rows = []
        return { body: { unlinked: true, unmanaged: false } }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '撤銷' }))

    // 還沒送：第一下只展開後果。
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/undo')).toBe(false)
    expect(within(row).getByText(/complete 裡的檔案不動/)).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: '確定撤銷' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/7/undo')).toBe(true)
  })

  it('撤銷時媒體庫裡那個檔案不是 Berth 放的，結果那一句說沒有刪它（M3 票 01）', async () => {
    let rows: ReviewQueue['rows'] = [audit()]
    render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/7/undo': () => {
        rows = []
        return { body: { unlinked: false, unmanaged: true } }
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '撤銷' }))
    await userEvent.click(within(row).getByRole('button', { name: '確定撤銷' }))

    expect(
      await screen.findByText(
        '已撤銷，這一筆下載回到待審核。媒體庫裡那個檔案已經不是 Berth 放的那一個，所以沒有刪。',
      ),
    ).toBeInTheDocument()
  })

  it('撤銷失敗時那一列留著，說出理由與原文', async () => {
    render({
      [QUEUE]: queue([audit()]),
      'POST /api/review/audit/7/undo': {
        status: 409,
        body: { detail: { reason: 'unlink_failed', detail: 'Permission denied' } },
      },
    })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '撤銷' }))
    await userEvent.click(within(row).getByRole('button', { name: '確定撤銷' }))

    expect(await within(row).findByRole('alert')).toHaveTextContent(
      '媒體庫裡那個檔案拿不掉，所以什麼都沒改。 Permission denied',
    )
  })

  it('沒有 Issue 列，原位一行「另有 N 件待處理」連到 /issues（M3 票 05）', async () => {
    render({ [QUEUE]: queue([audit()], 1, 2) })
    renderApp('/review')

    const link = await screen.findByRole('link', { name: '另有 2 件待處理' })

    expect(link).toHaveAttribute('href', '/issues')
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1)
  })

  it('佇列空了也照樣說還有幾件待處理', async () => {
    render({ [QUEUE]: queue([], 0, 1) })
    renderApp('/review')

    expect(await screen.findByText('沒有事在等你。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '另有 1 件待處理' })).toBeInTheDocument()
  })

  it('沒有 Issue 時那一行不出現', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')

    await screen.findByRole('article')
    expect(screen.queryByText(/件待處理/)).not.toBeInTheDocument()
  })

  it('超過上限時說出只列了前幾件', async () => {
    render({ [QUEUE]: queue([audit()], 201) })
    renderApp('/review')

    expect(await screen.findByText('只列出最舊的 1 件，共 201 件。')).toBeInTheDocument()
  })

  it('空的時候說沒有事在等你', async () => {
    render()
    renderApp('/review')

    expect(await screen.findByText('沒有事在等你。')).toBeInTheDocument()
  })
})

describe('收起時說出為什麼是 medium（M3 票 05）', () => {
  it('沒有降級理由時照舊說已自動入庫', async () => {
    render({
      [QUEUE]: queue([
        audit({ reasons: [{ code: 'season_from_release', params: { season: 2 } }] }),
      ]),
    })
    renderApp('/review')

    const row = await screen.findByRole('article')

    expect(within(row).getByText(/信心 medium，已自動入庫/)).toBeInTheDocument()
  })

  it('en 也說得出主要原因，參數照樣翻', async () => {
    await i18next.changeLanguage('en')
    try {
      render({
        [QUEUE]: queue([
          audit({ reasons: [{ code: 'strategy_outlier', params: { strategy: 'explicit' } }] }),
        ]),
      })
      renderApp('/review')

      const row = await screen.findByRole('article')

      expect(
        within(row).getByText(
          /Medium confidence: the rest of this batch was read by the name itself, this one was not/,
        ),
      ).toBeInTheDocument()
    } finally {
      await i18next.changeLanguage('zh-Hant')
    }
  })
})

describe('同一個 Job 一組一顆「全部確認」（M3 票 05）', () => {
  const pack = (): ReviewQueue['rows'] => [
    audit(),
    audit({ ref: 8, episode_start: 2 }),
    audit({ ref: 9, episode_start: 3 }),
  ]

  it('收成一列：作品是標題，組內原因相同就說一次，成員收在展開裡', async () => {
    render({ [QUEUE]: queue(pack()) })
    renderApp('/review')

    const [group] = await screen.findAllByRole('article')

    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(1)
    expect(within(group).getByRole('heading', { level: 3 })).toHaveTextContent(
      'SPY×FAMILY 間諜家家酒',
    )
    expect(
      within(group).getByText(/3 個檔案，信心 medium：集號是換算的（各季集數累加）/),
    ).toBeInTheDocument()
    // 整段那一顆不出現：audit 全在這一組裡，這一組的鍵就是它。
    expect(screen.getAllByRole('button', { name: '全部確認' })).toHaveLength(1)

    await userEvent.click(within(group).getAllByText('展開')[0])

    const members = within(group).getAllByRole('heading', { level: 4 })
    expect(members.map((node) => node.textContent)).toEqual(['S02E01', 'S02E02', 'S02E03'])
    // 組已經說過的那一句，成員不再說。
    expect(within(group).getAllByText(/集號是換算的/)).toHaveLength(1)
  })

  it('組內原因不同時說不只一種，每一個成員說自己的', async () => {
    render({
      [QUEUE]: queue([
        audit(),
        audit({ ref: 8, episode_start: 2, reasons: [{ code: 'single_season', params: {} }] }),
      ]),
    })
    renderApp('/review')

    const [group] = await screen.findAllByRole('article')

    expect(
      within(group).getByText(/2 個檔案信心 medium，原因不只一種，展開看每一個/),
    ).toBeInTheDocument()
    await userEvent.click(within(group).getAllByText('展開')[0])
    expect(within(group).getByText(/季號是推論的（TMDB 只有一季）/)).toBeInTheDocument()
  })

  it('按下去整組消失，送的是這一組的 id，看得見確認了幾個', async () => {
    let rows = pack()
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/confirm': () => {
        rows = []
        return { body: { confirmed: 3, skipped: 0 } }
      },
    })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    await userEvent.click(within(group).getByRole('button', { name: '全部確認' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(sentIds(stub)).toEqual([7, 8, 9])
    expect(screen.getByText('已確認 3 個，從佇列上收掉了。')).toBeVisible()
  })

  it('中途有一列已被撤銷時照樣成功，並說出跳過幾列', async () => {
    let rows = pack()
    render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/confirm': () => {
        rows = []
        return { body: { confirmed: 2, skipped: 1 } }
      },
    })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    await userEvent.click(within(group).getByRole('button', { name: '全部確認' }))

    expect(
      await screen.findByText('已確認 2 個，從佇列上收掉了。 1 個已經在別處確認或撤銷過，跳過了。'),
    ).toBeVisible()
  })

  it('成員仍然能單獨撤銷', async () => {
    const stub = render({
      [QUEUE]: queue(pack()),
      'POST /api/review/audit/8/undo': { body: { unlinked: true, unmanaged: false } },
    })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')
    await userEvent.click(within(group).getAllByText('展開')[0])
    const member = within(group).getAllByRole('article')[1]

    await userEvent.click(within(member).getByRole('button', { name: '撤銷' }))
    await userEvent.click(within(member).getByRole('button', { name: '確定撤銷' }))

    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => url === '/api/review/audit/8/undo')).toBe(true),
    )
  })
})

describe('audit 段整段的「全部確認」（M3 票 05）', () => {
  const twoJobs = (): ReviewQueue['rows'] => [
    audit(),
    audit({ ref: 8, episode_start: 2, job_hash: OTHER, job_name: 'another' }),
    duplicate(),
  ]

  it('先就地確認並說出件數，只算 audit、不算重複版本', async () => {
    const stub = render({ [QUEUE]: queue(twoJobs()) })
    renderApp('/review')
    const section = await screen.findByRole('region', { name: /已入庫，等你看一眼/ })
    const buttons = within(section).getAllByRole('button', { name: '全部確認' })

    // 兩列 audit 各自一筆下載：不成組，整段那一顆是唯一的一顆。
    expect(buttons).toHaveLength(1)
    await userEvent.click(buttons[0])

    expect(within(section).getByText(/這一段列出的 2 個已入庫檔案都會記成「對的」/)).toBeVisible()
    expect(sentIds(stub)).toBeNull()
    expect(within(section).getByRole('button', { name: '確認這 2 個' })).toBeInTheDocument()
  })

  it('只確認送出的那些 id，按下之後才進來的 audit 留在清單上', async () => {
    const arrived = audit({
      ref: 11,
      episode_start: 5,
      job_hash: 'c'.repeat(40),
      job_name: 'late',
    })
    let rows = twoJobs()
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/confirm': () => {
        // 畫面列出之後伺服器那一側又進來一個：確認完只剩它與那一件重複版本。
        rows = [arrived, duplicate()]
        return { body: { confirmed: 2, skipped: 0 } }
      },
    })
    renderApp('/review')
    const section = await screen.findByRole('region', { name: /已入庫，等你看一眼/ })

    await userEvent.click(within(section).getByRole('button', { name: '全部確認' }))
    await userEvent.click(within(section).getByRole('button', { name: '確認這 2 個' }))

    expect(await screen.findByText('已確認 2 個，從佇列上收掉了。')).toBeVisible()
    expect(sentIds(stub)).toEqual([7, 8])
    expect(
      await screen.findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒 S02E05' }),
    ).toBeVisible()
  })

  it('確認展開之後佇列才重問進來的 audit，不算在內、件數也不變', async () => {
    const arrived = audit({ ref: 11, episode_start: 5, job_hash: 'c'.repeat(40) })
    let rows = twoJobs()
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/confirm': () => {
        rows = [arrived, duplicate()]
        return { body: { confirmed: 2, skipped: 0 } }
      },
    })
    renderApp('/review')
    const section = await screen.findByRole('region', { name: /已入庫，等你看一眼/ })
    await userEvent.click(within(section).getByRole('button', { name: '全部確認' }))

    // 使用者讀著「這 2 個」的時候切回視窗，佇列重問，多了一個。
    rows = [...twoJobs().slice(0, 2), arrived, duplicate()]
    focusManager.setFocused(false)
    focusManager.setFocused(true)
    await within(section).findByRole('heading', { name: 'SPY×FAMILY 間諜家家酒 S02E05' })

    expect(within(section).getByText(/這一段列出的 2 個已入庫檔案/)).toBeVisible()
    await userEvent.click(within(section).getByRole('button', { name: '確認這 2 個' }))

    await waitFor(() => expect(sentIds(stub)).toEqual([7, 8]))
    focusManager.setFocused(undefined)
  })

  it('只有一列 audit 時不給整段的鍵', async () => {
    render({ [QUEUE]: queue([audit(), duplicate()]) })
    renderApp('/review')

    await screen.findAllByRole('article')

    expect(screen.queryByRole('button', { name: '全部確認' })).not.toBeInTheDocument()
  })
})

describe('誰看得到審核佇列', () => {
  it('admin 的導覽列有入口', async () => {
    render()
    renderApp('/review')

    expect(await screen.findByRole('link', { name: '審核' })).toBeInTheDocument()
  })

  it('user 看不到入口，直接開網址會被送走', async () => {
    render({ 'GET /api/auth/me': { body: { name: 'deckhand', role: 'user' } } })
    const { router } = renderApp('/review')

    await waitFor(() => expect(router.state.location.pathname).toBe('/health'))
    expect(screen.queryByRole('link', { name: '審核' })).not.toBeInTheDocument()
  })
})

import { focusManager } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18next from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AuditReviewRow, DuplicateReviewRow, ReviewQueue } from '../api/review'
import { HEALTHY, UNAUTHORIZED, session, stubApi, type StubRoute } from '../test/fetch'
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
    // 與後端同一條（`review._audit_row`）：還沒確認的 RSS Series 送的就是第一批。
    reason: {
      code:
        overrides.series && !overrides.series.confirmed ? 'first_batch' : 'medium_auto_imported',
      params: {},
    },
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
    action: 'import',
    series: null,
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

  // M2 票 16 critique P2（M3 票 06）：每一列的「展開」原本都只叫「展開」，一頁五件就是五顆同名的鍵。
  it('每一列的「展開」說得出是哪一件', async () => {
    render({ [QUEUE]: queue([audit(), duplicate()]) })
    renderApp('/review')

    const [first, second] = await screen.findAllByRole('article')
    const summaryOf = (row: HTMLElement) => within(row).getByText('展開').closest('summary')

    expect(summaryOf(first)).toHaveAccessibleName('展開 SPY×FAMILY 間諜家家酒 S02E01')
    expect(summaryOf(second)).toHaveAccessibleName(/^展開 SPY×FAMILY 間諜家家酒/)
    expect(summaryOf(second)).not.toHaveAccessibleName(summaryOf(first)?.textContent ?? '')
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
    const headings = screen.getAllByRole('heading', { level: 2 })

    // 光一個數字念出來沒有意義：聽得見的是帶單位的那一句（M2 票 16 audit P3，M3 票 06）。
    expect(headings).toHaveLength(1)
    expect(headings[0]).toHaveAccessibleName('已入庫，等你看一眼 2 件')
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

/** 送出那一列的 RSS Series：預設還沒確認、兩格都沒設（剛綁好、第一批）。 */
function series(overrides: Partial<NonNullable<AuditReviewRow['series']>> = {}) {
  return {
    id: 3,
    // 長出它的那一筆 Item 的標題（看得出字幕組），不是哪一筆下載的名字。
    name: '[ANi] SPY×FAMILY 間諜家家酒 - 25 [1080P][Baha][WEB-DL]',
    group: 'ANi',
    confirmed: false,
    season: null,
    episode_offset: null,
    ask: null,
    ...overrides,
  }
}

/** 某一支 POST 送出去的 body；還沒送是 `undefined`。 */
function bodyOf(stub: ReturnType<typeof render>, url: string): unknown {
  const call = stub.mock.calls.find(([called]) => called === url)
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

describe('RSS Series 的第一批（M3 票 13）', () => {
  // 補舊集一次送好幾筆下載、一集一個 Job：以 Job 分組等於不分，這裡以 Series 分組。
  const firstBatch = (): ReviewQueue['rows'] =>
    [7, 8, 9].map((ref, index) =>
      audit({
        ref,
        episode_start: index + 1,
        job_hash: String(ref).repeat(40),
        reason: { code: 'first_batch', params: {} },
        series: series(),
      }),
    )

  it('一個 Series 一組：說出是第一批，展開看得到 Series 與它現在的季號、偏移', async () => {
    render({ [QUEUE]: queue(firstBatch()) })
    renderApp('/review')

    const [group] = await screen.findAllByRole('article')

    expect(within(group).getByRole('heading', { level: 3 })).toHaveTextContent(
      'SPY×FAMILY 間諜家家酒',
    )
    expect(
      within(group).getByText(/RSS Series 的第一批：3 個檔案等你看一眼季號與集數對不對/),
    ).toBeInTheDocument()

    await userEvent.click(within(group).getAllByText('展開')[0])

    expect(within(group).getByText(series().name)).toBeInTheDocument()
    expect(within(group).getByText('沒有設，由解析器判斷')).toBeInTheDocument()
    expect(
      within(group)
        .getAllByRole('heading', { level: 4 })
        .map((node) => node.textContent),
    ).toEqual(['S02E01', 'S02E02', 'S02E03'])
    // 組說過的那一句，成員不再說。
    expect(within(group).getAllByText(/RSS Series 的第一批/)).toHaveLength(1)
  })

  it('Series 設過季號與偏移時，展開說出現在的值', async () => {
    const values = series({ season: 1, episode_offset: 12 })
    render({ [QUEUE]: queue(firstBatch().map((row) => ({ ...row, series: values }))) })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    await userEvent.click(within(group).getAllByText('展開')[0])

    expect(within(group).getByText('第 1 季、集號偏移 +12')).toBeInTheDocument()
  })

  it('後端說得出在問什麼時，整組一句話：作品 × 字幕組、哪幾集、季集怎麼讀出來（M4 票 11）', async () => {
    const asking = series({ ask: { spans: [{ season: 2, start: 1, end: 3 }], basis: 'literal' } })
    render({ [QUEUE]: queue(firstBatch().map((row) => ({ ...row, series: asking }))) })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    expect(
      within(group).getByText(
        '確認 SPY×FAMILY 間諜家家酒 × ANi 的季集對應：S02 E01–E03 由集號直接對應',
      ),
    ).toBeInTheDocument()
    expect(within(group).queryByText(/RSS Series 的第一批/)).not.toBeInTheDocument()
    expect(within(group).getByRole('button', { name: '確認整個 Series' })).toBeInTheDocument()
    // 逐列展開留著。
    await userEvent.click(within(group).getAllByText('展開')[0])
    expect(within(group).getAllByRole('heading', { level: 4 })).toHaveLength(3)
  })

  it('「確認整個 Series」打 Series 那一支，送的是畫面上的 id', async () => {
    let rows = firstBatch()
    const stub = render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/series/3/confirm': () => {
        rows = []
        return { body: { confirmed: 3, skipped: 0 } }
      },
    })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    await userEvent.click(within(group).getByRole('button', { name: '確認整個 Series' }))

    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(bodyOf(stub, '/api/review/series/3/confirm')).toEqual({ ledger_ids: [7, 8, 9] })
    expect(sentIds(stub)).toBeNull()
    expect(screen.getByText('已確認 3 個，從佇列上收掉了。')).toBeVisible()
  })

  it('第一批只有一集時仍是一組：組的鍵確認整個 Series，不只清那一列的旗標', async () => {
    const stub = render({
      [QUEUE]: queue(firstBatch().slice(0, 1)),
      'POST /api/review/series/3/confirm': { body: { confirmed: 1, skipped: 0 } },
    })
    renderApp('/review')
    const [group] = await screen.findAllByRole('article')

    expect(within(group).getByText(/RSS Series 的第一批：1 個檔案/)).toBeInTheDocument()
    await userEvent.click(within(group).getByRole('button', { name: '確認整個 Series' }))

    await waitFor(() =>
      expect(bodyOf(stub, '/api/review/series/3/confirm')).toEqual({ ledger_ids: [7] }),
    )
  })

  it('整段的「全部確認」：Series 的列送 Series 那一支、其餘送一般那一支，按之前說出第一批會一起確認', async () => {
    const stub = render({
      [QUEUE]: queue([...firstBatch(), audit({ ref: 20, job_hash: OTHER })]),
      'POST /api/review/series/3/confirm': { body: { confirmed: 3, skipped: 0 } },
      'POST /api/review/audit/confirm': { body: { confirmed: 1, skipped: 0 } },
    })
    renderApp('/review')
    const section = await screen.findByRole('region', { name: /已入庫，等你看一眼/ })
    const [sectionButton] = within(section).getAllByRole('button', { name: '全部確認' })

    await userEvent.click(sectionButton)
    expect(within(section).getByText(/其中 1 個 RSS Series 的第一批一起確認/)).toBeVisible()
    await userEvent.click(within(section).getByRole('button', { name: '確認這 4 個' }))

    expect(await screen.findByText('已確認 4 個，從佇列上收掉了。')).toBeVisible()
    expect(bodyOf(stub, '/api/review/series/3/confirm')).toEqual({ ledger_ids: [7, 8, 9] })
    expect(sentIds(stub)).toEqual([20])
  })

  it('確認過的 Series 只有一列時就是一列，沒有第一批那一句', async () => {
    render({ [QUEUE]: queue([audit({ series: series({ confirmed: true }) })]) })
    renderApp('/review')

    const row = await screen.findByRole('article')

    expect(within(row).getByRole('heading')).toHaveTextContent('SPY×FAMILY 間諜家家酒 S02E01')
    expect(within(row).queryByText(/第一批/)).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: '全部確認' })).not.toBeInTheDocument()
  })
})

describe('改季集，並套用到這個 RSS Series（M3 票 13）', () => {
  const REMATCH = 'POST /api/files/rematch'
  const corrected = (moved: number): StubRoute => ({
    body: {
      plan_id: 30,
      target_path: '/x/S01E13.mkv',
      unmanaged: [],
      series: { season: 1, episode_offset: 12, moved, replanned: 0, left: 0 },
    },
  })

  /** 一個 Series 的第一批是一組：展開那一組，回第一個成員。 */
  async function firstMember() {
    const [group] = await screen.findAllByRole('article')
    await userEvent.click(within(group).getAllByText('展開')[0])
    return within(group).getAllByRole('article')[0]
  }

  /** 填季集、按「套用」（已入庫的檔案接著要就地確認）。 */
  async function fill(row: HTMLElement, season: string, episode: string) {
    const seasonField = within(row).getByRole('spinbutton', { name: '季' })
    await userEvent.clear(seasonField)
    await userEvent.type(seasonField, season)
    const startField = within(row).getByRole('spinbutton', { name: '起集' })
    await userEvent.clear(startField)
    await userEvent.type(startField, episode)
    await userEvent.click(within(row).getByRole('button', { name: '套用' }))
  }

  it('Series 送的正片：預設勾著套用，就地確認說搬的不只這一集，送 apply_to_series，看得見其餘跟著搬了幾集', async () => {
    const stub = render({
      [QUEUE]: queue([
        audit({ reason: { code: 'first_batch', params: {} }, series: series() }),
        audit({ ref: 8, episode_start: 2, job_hash: OTHER, series: series() }),
      ]),
      [REMATCH]: corrected(1),
    })
    renderApp('/review')
    const row = await firstMember()

    await userEvent.click(within(row).getByRole('button', { name: '改季集 S02E01' }))
    const apply = within(row).getByRole('checkbox', { name: '套用到這個 RSS Series' })
    expect(apply).toBeChecked()
    expect(apply).toHaveAccessibleDescription(/重算這個 Series 還沒確認的集數/)

    await fill(row, '1', '13')
    expect(within(row).getByText(/還沒確認的其他集數也照新的季號與偏移搬過去/)).toBeVisible()
    await userEvent.click(within(row).getByRole('button', { name: '確定修正' }))

    expect(
      await screen.findByText(
        '已修正，這個 RSS Series 改成第 1 季、集號偏移 +12。 其餘 1 集跟著搬過去了。',
      ),
    ).toBeVisible()
    expect(bodyOf(stub, '/api/files/rematch')).toEqual({
      ledger_id: 7,
      action: 'import',
      season: 1,
      episode_start: 13,
      episode_end: null,
      apply_to_series: true,
    })
  })

  it('取消勾選時只改這一集：不帶 apply_to_series，就地確認照舊', async () => {
    const stub = render({
      [QUEUE]: queue([audit({ series: series() })]),
      [REMATCH]: { body: { plan_id: 30, target_path: '/x.mkv', unmanaged: [], series: null } },
    })
    renderApp('/review')
    const row = await firstMember()

    await userEvent.click(within(row).getByRole('button', { name: /^改季集/ }))
    await userEvent.click(within(row).getByRole('checkbox', { name: '套用到這個 RSS Series' }))
    await fill(row, '2', '1')
    expect(
      within(row).getByText(/媒體庫裡現在這一條會被拿掉、換到新的位置；旁邊的字幕跟著走/),
    ).toBeVisible()
    await userEvent.click(within(row).getByRole('button', { name: '確定修正' }))

    expect(await screen.findByText('已修正。')).toBeInTheDocument()
    expect(bodyOf(stub, '/api/files/rematch')).not.toHaveProperty('apply_to_series')
  })

  it('不是 Series 送的正片也改得了季集，帶著現在的季集，但沒有套用那一格', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '改季集 S02E01' }))

    expect(within(row).getByRole('spinbutton', { name: '季' })).toHaveValue(2)
    expect(within(row).getByRole('spinbutton', { name: '起集' })).toHaveValue(1)
    expect(within(row).queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('再按一次「改季集」收起表單，焦點回到那顆鍵', async () => {
    render({ [QUEUE]: queue([audit()]) })
    renderApp('/review')
    const row = await screen.findByRole('article')
    const trigger = within(row).getByRole('button', { name: '改季集 S02E01' })

    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(within(row).getByRole('button', { name: '取消' }))

    expect(within(row).queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
  })

  it('字幕與特典沒有「改季集」', async () => {
    render({ [QUEUE]: queue([audit({ action: 'subtitle' })]) })
    renderApp('/review')
    const row = await screen.findByRole('article')

    expect(within(row).queryByRole('button', { name: /^改季集/ })).not.toBeInTheDocument()
  })

  it('算不出偏移時說得出下一步', async () => {
    render({
      [QUEUE]: queue([audit({ series: series() })]),
      [REMATCH]: {
        status: 422,
        body: { detail: { reason: 'no_episode_number', detail: 'a.mkv' } },
      },
    })
    renderApp('/review')
    const row = await firstMember()

    await userEvent.click(within(row).getByRole('button', { name: /^改季集/ }))
    await fill(row, '1', '13')
    await userEvent.click(within(row).getByRole('button', { name: '確定修正' }))

    expect(await within(row).findByText(/檔名讀不出集號，算不出集號偏移。.*a\.mkv/)).toBeVisible()
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

/**
 * 審核之後 Media 詳情的入庫狀態要跟著變（M3 票 06）：那一份快取 5 分鐘內不重抓（`api/media.ts`），
 * 不讓它失效的話，從審核頁走回詳情頁看到的是按之前的樣子。
 */
describe('按完之後詳情頁不停在舊的入庫狀態', () => {
  const MEDIA = ['media', 'tv:120089']

  it.each([
    ['確認', 'POST /api/review/audit/7/confirm', { status: 204, body: null }, []],
    [
      '撤銷',
      'POST /api/review/audit/7/undo',
      { body: { unlinked: true, unmanaged: false } },
      ['確定撤銷'],
    ],
  ] as const)('%s', async (button, endpoint, reply, confirm) => {
    let rows: ReviewQueue['rows'] = [audit()]
    render({
      [QUEUE]: () => queue(rows),
      [endpoint]: () => {
        rows = []
        return reply
      },
    })
    const { queryClient } = renderApp('/review')
    queryClient.setQueryData(MEDIA, { id: 'tv:120089' })
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: button }))
    for (const name of confirm) await userEvent.click(within(row).getByRole('button', { name }))

    await waitFor(() => expect(queryClient.getQueryState(MEDIA)?.isInvalidated).toBe(true))
  })

  it('整組確認', async () => {
    let rows: ReviewQueue['rows'] = [audit(), audit({ ref: 8, episode_start: 2 })]
    render({
      [QUEUE]: () => queue(rows),
      'POST /api/review/audit/confirm': () => {
        rows = []
        return { body: { confirmed: 2, skipped: 0 } }
      },
    })
    const { queryClient } = renderApp('/review')
    queryClient.setQueryData(MEDIA, { id: 'tv:120089' })

    await userEvent.click(await screen.findByRole('button', { name: '全部確認' }))

    await waitFor(() => expect(queryClient.getQueryState(MEDIA)?.isInvalidated).toBe(true))
  })
})

/**
 * 任何請求回 401 就導回登入頁、登入後回到原本那一頁（M3 票 06）。之前只有路由守衛會問 `GET /auth/me`：
 * session 在頁面上失效之後，讀資料與按鈕各自說「失敗了」，人卡在一頁什麼都做不了的畫面上。
 */
describe('session 在頁面上失效', () => {
  function signedIn() {
    const backend = session({ name: 'skipper', role: 'admin' })
    return {
      backend,
      routes: {
        'GET /api/health': { body: HEALTHY },
        'GET /api/auth/me': () => backend.me(),
        'POST /api/auth/login': backend.signIn({ name: 'skipper', role: 'admin' }),
      },
    }
  }

  it('讀資料回 401：導到登入頁並說已過期，登入之後回到這一頁', async () => {
    const { backend, routes } = signedIn()
    stubApi({
      ...routes,
      [QUEUE]: () => (backend.me().status === 401 ? UNAUTHORIZED : queue([audit()])),
    })
    const { router, queryClient } = renderApp('/review')
    await screen.findByRole('article')

    backend.signOut()
    await queryClient.invalidateQueries({ queryKey: ['review'] })

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/review', expired: true })

    await userEvent.type(await screen.findByLabelText('帳號'), 'skipper')
    await userEvent.type(screen.getByLabelText('密碼'), 'harbour')
    await userEvent.click(screen.getByRole('button', { name: '登入' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/review'))
    expect(await screen.findByRole('article')).toBeInTheDocument()
  })

  it('按鈕回 401：一樣導到登入頁', async () => {
    const { backend, routes } = signedIn()
    stubApi({
      ...routes,
      [QUEUE]: queue([audit()]),
      'POST /api/review/audit/7/confirm': () => {
        backend.signOut()
        return UNAUTHORIZED
      },
    })
    const { router } = renderApp('/review')
    const row = await screen.findByRole('article')

    await userEvent.click(within(row).getByRole('button', { name: '確認' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toEqual({ redirect: '/review', expired: true })
  })
})

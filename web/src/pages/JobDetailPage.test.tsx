import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Job, JobEvent } from '../api/jobs'
import type { Plan } from '../api/plans'
import { HEALTHY, stubApi, type StubRoute } from '../test/fetch'
import { renderApp } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

const HASH = '4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b'
const JOB = `GET /api/jobs/${HASH}`
const EVENTS = `GET /api/jobs/${HASH}/events`
const PLAN = 'GET /api/plans/7'

function job(overrides: Partial<Job> = {}): Job {
  return {
    hash: HASH,
    name: '[ANi] SPY×FAMILY - 13 [1080P][WEB-DL][AAC AVC][CHT]',
    state: 'imported',
    trigger: 'manual',
    trigger_ref: '',
    error: '',
    media_id: 'tv:120089',
    media_title: 'SPY×FAMILY 間諜家家酒',
    media_title_en: 'SPY x FAMILY',
    route_id: 2,
    route_name: 'Anime',
    route_slug: 'anime',
    user_id: 1,
    user_name: 'skipper',
    save_path: '/data/torrent/complete/anime',
    content_path: '',
    total_size: 1_400_000_000,
    progress: 1,
    client_state: 'uploading',
    added_at: '2026-09-10T12:00:00Z',
    completed_at: '2026-09-10T13:00:00Z',
    imported_at: '2026-09-10T13:05:00Z',
    retryable: false,
    replannable: false,
    reimportable: false,
    plan_id: 7,
    audits: 0,
    ...overrides,
  }
}

function event(id: number, type: string, payload: JobEvent['payload'] = {}): JobEvent {
  return { id, type, actor: 'system', payload, created_at: `2026-09-10T12:0${id}:00Z` }
}

/** 一筆從送單走到入庫、中間被管理員修正過一個檔案的 Job。 */
const HISTORY: JobEvent[] = [
  event(1, 'created', { route: 'anime', trigger: 'manual' }),
  event(2, 'submitted', { category: 'berth-anime', save_path: '/data/torrent/complete/anime' }),
  event(3, 'plan_generated', { engine: 'rules', files: 1, high: 1, medium: 0, low: 0 }),
  event(4, 'linked', {
    file: 'a.mkv',
    target: '/data/library/anime/Show/Season 01/Show - S01E13.mkv',
  }),
  event(5, 'rematched', {
    plan: 12,
    file: 'a.mkv',
    from: { action: 'import', season: 1, episode_start: 13, episode_end: null, target: '' },
    to: { action: 'extra', season: null, episode_start: null, episode_end: null, target: '' },
  }),
]

function plan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 7,
    job_hash: HASH,
    status: 'applied',
    engine: 'rules',
    engine_version: '0.1.0',
    created_at: '2026-09-10T13:00:00Z',
    media_kind: 'tv',
    summary: { files: 1, high: 1, medium: 0, low: 0, actions: { import: 1 }, review_reason: null },
    items: [
      {
        id: 1,
        rel_path: '[ANi] SPY×FAMILY - 13.mkv',
        kind: 'video',
        action: 'import',
        media_id: 'tv:120089',
        season: 1,
        episode_start: 13,
        episode_end: null,
        target_path: '/data/library/anime/Show/Season 01/Show - S01E13.mkv',
        confidence: 'high',
        reasons: [],
        audit: false,
        applied: true,
        actions: [],
        error: '',
      },
    ],
    ...overrides,
  }
}

/** 刪除的確認區打開時問的那一份（M2 票 04）。這一頁只在乎它掛的是不是那一個元件。 */
const ESTIMATE = {
  links: 1,
  links_missing: 0,
  link_bytes: 0,
  sources: 1,
  sources_missing: 0,
  source_bytes: 0,
  reclaimable: 0,
  held: 0,
}

const ADMIN = { body: { name: 'skipper', role: 'admin' } }
const USER = { body: { name: 'deckhand', role: 'user' } }

function render(routes: Record<string, StubRoute | (() => StubRoute)> = {}) {
  return stubApi({
    'GET /api/health': { body: HEALTHY },
    'GET /api/auth/me': ADMIN,
    [JOB]: { body: job() },
    [EVENTS]: { body: HISTORY },
    [PLAN]: { body: plan() },
    [`GET /api/jobs/${HASH}/deletion`]: { body: ESTIMATE },
    ...routes,
  })
}

/** 標題是 `h2` 的那一段。 */
async function section(name: string) {
  const heading = await screen.findByRole('heading', { level: 2, name })
  const region = heading.closest('section')
  if (!region) throw new Error(`no section around ${name}`)
  return region
}

describe('Job 詳情頁（M2 票 12）', () => {
  it('貼網址直接進得來：發佈名是這一頁的標題，作品連回它的頁面', async () => {
    render()
    renderApp(`/jobs/${HASH}`)

    expect(
      await screen.findByRole('heading', { level: 1, name: /SPY×FAMILY - 13/ }),
    ).toBeInTheDocument()
    expect(screen.getByText('已入庫')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'SPY×FAMILY 間諜家家酒' })).toHaveAttribute(
      'href',
      expect.stringMatching(/^\/media\/tv(:|%3A)120089$/),
    )
    expect(screen.getByRole('link', { name: '回下載列表' })).toHaveAttribute('href', '/jobs')
  })

  it('檔案與決策是那一份計劃：逐檔說得出會落在哪', async () => {
    render()
    renderApp(`/jobs/${HASH}`)

    const files = await section('檔案與決策')
    await userEvent.click(await within(files).findByText('1 個檔案'))

    expect(within(files).getByText('[ANi] SPY×FAMILY - 13.mkv')).toBeInTheDocument()
    expect(
      within(files).getByText('/data/library/anime/Show/Season 01/Show - S01E13.mkv'),
    ).toBeInTheDocument()
  })

  it('計劃歷史只收那份決定怎麼變成現在這樣的事件，送單與鏈接不在裡面', async () => {
    render()
    renderApp(`/jobs/${HASH}`)

    const history = await section('計劃歷史')

    expect(await within(history).findByText('已修正')).toBeInTheDocument()
    expect(within(history).getByText('計劃')).toBeInTheDocument()
    expect(within(history).queryByText('已送出')).toBeNull()
    expect(within(history).queryByText('已鏈接')).toBeNull()
  })

  it('完整的時間線另一段，每一筆都在', async () => {
    render()
    renderApp(`/jobs/${HASH}`)

    const timeline = await section('時間線')

    expect(await within(timeline).findByText('已送出')).toBeInTheDocument()
    expect(within(timeline).getByText('已鏈接')).toBeInTheDocument()
    expect(within(timeline).getByText('已修正')).toBeInTheDocument()
  })

  it('還沒算過計劃的那一筆連問都不問，說出什麼時候才會有', async () => {
    const stub = render({
      [JOB]: { body: job({ state: 'downloading', plan_id: null }) },
      [EVENTS]: { body: [HISTORY[0]] },
    })
    renderApp(`/jobs/${HASH}`)

    const files = await section('檔案與決策')

    expect(within(files).getByText(/還沒有計劃/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '計劃歷史' })).toBeNull()
    expect(stub.mock.calls.some(([url]) => String(url).includes('/plans/'))).toBe(false)
  })

  it('不存在的 hash 說得出可能的原因與回去的路，不是一片空白', async () => {
    render({ [JOB]: { status: 404, body: { detail: 'no such job' } } })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByRole('heading', { level: 1, name: '找不到這筆下載' })).toBeVisible()
    expect(screen.getByText(/已經被刪除並清除了紀錄/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '回下載列表' })).toHaveAttribute('href', '/jobs')
  })

  it('後端問不到時說的是 Berth 自己，不當成找不到', async () => {
    render({ [JOB]: { status: 500, body: { detail: 'boom' } } })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByText(/讀不到這筆下載/)).toBeInTheDocument()
    expect(screen.queryByText('找不到這筆下載')).toBeNull()
  })
})

describe('詳情頁的動作', () => {
  it('刪除是票 04 那一個元件：展開之後是四個旗標與估算', async () => {
    const stub = render()
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '刪除' }))

    const panel = screen.getByRole('group', { name: '要刪掉哪幾樣' })
    expect(within(panel).getAllByRole('checkbox')).toHaveLength(4)
    // 估算是打開那一刻才問的（`deletionQueryOptions`）。不按確認：這一條不真的刪。
    await waitFor(() =>
      expect(stub.mock.calls.some(([url]) => String(url).endsWith('/deletion'))).toBe(true),
    )
    expect(stub.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  })

  it('勾了清除紀錄刪完，這一頁就是「找不到這筆下載」——那一筆已經不在了', async () => {
    let gone = false
    render({
      [JOB]: () => (gone ? { status: 404, body: { detail: 'no such job' } } : { body: job() }),
      [`DELETE /api/jobs/${HASH}?unlink=false&remove_torrent=false&delete_files=false&purge=true`]:
        () => {
          gone = true
          return { body: { links: 0, sources: 0, torrent: false, purged: true, freed: 0 } }
        },
    })
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '刪除' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /清除帳本與這一筆的紀錄/ }))
    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    expect(await screen.findByRole('heading', { level: 1, name: '找不到這筆下載' })).toBeVisible()
  })

  it('沒勾清除紀錄刪完，這一筆留在頁上、狀態換成已刪除，並說出真的做掉了什麼', async () => {
    let removed = false
    render({
      [JOB]: () => ({ body: job(removed ? { state: 'removed' } : {}) }),
      [`DELETE /api/jobs/${HASH}?unlink=true&remove_torrent=false&delete_files=false&purge=false`]:
        () => {
          removed = true
          return { body: { links: 1, sources: 0, torrent: false, purged: false, freed: 0 } }
        },
    })
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '刪除' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /移除媒體庫裡的硬鏈接/ }))
    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    expect(await screen.findByText('已刪除')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: /SPY×FAMILY - 13/ })).toBeInTheDocument()
  })

  it('送單失敗那一筆有原文與一顆重試；被擋下來時說那個理由', async () => {
    render({
      [JOB]: {
        body: job({
          state: 'submit_failed',
          error: 'torrents/add: connection refused',
          retryable: true,
          plan_id: null,
        }),
      },
      [EVENTS]: { body: [] },
      [`POST /api/jobs/${HASH}/retry`]: {
        status: 409,
        body: { detail: { reason: 'route_unhealthy', detail: 'anime' } },
      },
    })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByText('torrents/add: connection refused')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新送單' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/那條 Route 現在是紅的/)
  })

  it('入庫失敗那一筆的重試說的是「再試一次入庫」', async () => {
    render({ [JOB]: { body: job({ state: 'import_failed', retryable: true }) } })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByRole('button', { name: '再試一次入庫' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重新送單' })).toBeNull()
  })

  it('停在待審核的那一筆按得了重新規劃，按下去那一筆自己重問', async () => {
    const stub = render({
      [JOB]: { body: job({ state: 'review', replannable: true }) },
      [`POST /api/jobs/${HASH}/replan`]: { body: job({ state: 'planning' }) },
    })
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '重新規劃' }))

    await waitFor(() => {
      expect(
        stub.mock.calls.filter(([url]) => String(url) === `/api/jobs/${HASH}`).length,
      ).toBeGreaterThanOrEqual(2)
    })
  })

  it('重新規劃被擋下來時說的是那個理由', async () => {
    render({
      [JOB]: { body: job({ state: 'review', replannable: true }) },
      [`POST /api/jobs/${HASH}/replan`]: {
        status: 409,
        body: { detail: { reason: 'not_replannable', detail: 'importing' } },
      },
    })
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '重新規劃' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/不能重新規劃/)
  })

  it('admin 在入庫完的那一筆按得了重新入庫；被擋下來時照理由說', async () => {
    render({
      [JOB]: { body: job({ reimportable: true }) },
      [`POST /api/jobs/${HASH}/reimport`]: {
        status: 409,
        body: { detail: { reason: 'content_missing', detail: '/data/torrent/complete/anime/x' } },
      },
    })
    renderApp(`/jobs/${HASH}`)

    await userEvent.click(await screen.findByRole('button', { name: '重新入庫' }))

    expect(await screen.findByText(/complete 裡已經沒有這一包了/)).toBeInTheDocument()
  })

  it('admin 在待審核的那一筆看到去處理它的路', async () => {
    render({ [JOB]: { body: job({ state: 'review' }) } })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByRole('link', { name: '到審核佇列處理' })).toHaveAttribute(
      'href',
      '/review',
    )
    expect(screen.queryByText('等管理員審核')).toBeNull()
  })
})

describe('一般使用者進得來，但刪除與重新入庫不是給他的（brief §11）', () => {
  it('看得到自己那一筆的全部內容，沒有刪除與重新入庫', async () => {
    // **前端隱藏不是安全機制**：擋住的那一條在門禁上（`DELETE /jobs/{hash}`、`GET …/deletion` 與
    // `POST /jobs/{hash}/reimport` 回 403，而 `GET /jobs/{hash}` 照常：`tests/integration/test_jobs_api.py`
    // 的 `TestDelete` / `TestReimport`，與 `test_auth_api.py` 的方法層級門禁那一組）。
    render({
      'GET /api/auth/me': USER,
      [JOB]: {
        body: job({
          state: 'import_failed',
          retryable: true,
          replannable: true,
          reimportable: true,
        }),
      },
    })
    renderApp(`/jobs/${HASH}`)

    // 時間線畫出來了才代表這一頁真的畫完了——否則下面兩條在任何情況下都會綠。
    await within(await section('時間線')).findByText('已送出')
    expect(screen.queryByRole('button', { name: '刪除' })).toBeNull()
    expect(screen.queryByRole('button', { name: '重新入庫' })).toBeNull()
    // 重試與重新規劃是他的（後端不擋），同一頁上照樣按得到。
    expect(screen.getByRole('button', { name: '再試一次入庫' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新規劃' })).toBeInTheDocument()
  })

  it('停在待審核時說「等管理員審核」，沒有去審核佇列的路', async () => {
    render({ 'GET /api/auth/me': USER, [JOB]: { body: job({ state: 'review' }) } })
    renderApp(`/jobs/${HASH}`)

    expect(await screen.findByText('等管理員審核')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '到審核佇列處理' })).toBeNull()
  })
})

import { describe, expect, it } from 'vitest'

import type { RssSeries } from '../api/rss'
import { byWork, groupName, mikanPage, sourceLabel, workTitle } from './seriesByWork'

function series(overrides: Partial<RssSeries> = {}): RssSeries {
  return {
    id: 7,
    key: 'mikan:4009:370',
    title_raw: '[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 - 11 [WebRip 1080p]',
    mikan_bangumi_id: 4009,
    mikan_subgroup_id: 370,
    mikan_bangumi_name: '与你相恋到生命尽头',
    mikan_subgroup_name: 'LoliHouse',
    media_id: 'tv:262000',
    media_title: '與妳相戀到生命盡頭',
    media_title_en: 'Kimishinu',
    route_id: 3,
    route_name: 'Anime',
    season: null,
    episode_offset: null,
    bound_by: 'system',
    waiting: 0,
    reasons: [],
    candidates: [],
    exclusions: [],
    confirmed: true,
    source: 'mikan',
    group: '喵萌奶茶屋&LoliHouse',
    latest_title: '',
    latest_at: null,
    latest_episode: null,
    imported: 0,
    active: 0,
    excluded: 0,
    finished: false,
    submitted: 0,
    ask: null,
    ...overrides,
  }
}

/** 照 key 念成字：`sourceLabel` 收的是 i18next 的 `t`，這裡只要看得出挑了哪一句。 */
const t = ((key: string, values?: Record<string, unknown>) =>
  values ? `${key}:${JSON.stringify(values)}` : key) as Parameters<typeof sourceLabel>[0]

describe('sourceLabel：來源說名字，不說 Mikan 的數字 id', () => {
  it('番組名與字幕組名都有', () => {
    expect(sourceLabel(t, series())).toBe(
      'rss.source.mikanGroup:{"bangumi":"与你相恋到生命尽头","group":"LoliHouse"}',
    )
  })

  it('字幕組那一格已經在列上時只說番組', () => {
    expect(sourceLabel(t, series(), { group: false })).toBe(
      'rss.source.mikan:{"bangumi":"与你相恋到生命尽头"}',
    )
  })

  it('只有番組名', () => {
    expect(sourceLabel(t, series({ mikan_subgroup_name: '' }))).toBe(
      'rss.source.mikan:{"bangumi":"与你相恋到生命尽头"}',
    )
  })

  it('名字都沒讀到時只說 Mikan，不退回 id 或鍵', () => {
    const label = sourceLabel(t, series({ mikan_bangumi_name: '', mikan_subgroup_name: '' }))
    expect(label).toBe('rss.source.mikanBare')
    expect(label).not.toMatch(/4009|370/)
  })

  it('不是 Mikan 的說站名', () => {
    const row = series({ key: 'title:kamiina:lolihouse', mikan_bangumi_id: null, source: 'nyaa' })
    expect(sourceLabel(t, row)).toBe('rss.kind.nyaa')
    expect(sourceLabel(t, series({ mikan_bangumi_id: null, source: null }))).toBe('—')
  })
})

describe('mikanPage', () => {
  it('番組頁的網址（id 只在 href 裡）', () => {
    expect(mikanPage(series())).toBe('https://mikanani.me/Home/Bangumi/4009#370')
    expect(mikanPage(series({ mikan_bangumi_id: null }))).toBeNull()
  })
})

describe('groupName', () => {
  it('Mikan 的字幕組名優先，其次發佈名讀出的，都沒有是空字串', () => {
    expect(groupName(series())).toBe('LoliHouse')
    expect(groupName(series({ mikan_subgroup_name: '' }))).toBe('喵萌奶茶屋&LoliHouse')
    expect(groupName(series({ mikan_subgroup_name: '', group: '' }))).toBe('')
  })
})

describe('workTitle', () => {
  it('跟著 UI 語言，兩輪都沒有時退回作品 id', () => {
    expect(workTitle('zh-Hant', series())).toBe('與妳相戀到生命盡頭')
    expect(workTitle('en', series())).toBe('Kimishinu')
    expect(workTitle('en', series({ media_title: '', media_title_en: '' }))).toBe('tv:262000')
  })
})

describe('byWork：作品一塊、字幕組一列，完結的另成一份', () => {
  it('同一部作品的兩個字幕組併成一塊，塊照第一次出現的順序', () => {
    const rows = [
      series({ id: 1 }),
      series({ id: 2, media_id: 'tv:1', media_title: 'BLACK TORCH' }),
      series({ id: 3, mikan_subgroup_name: 'ANi' }),
    ]
    const { active, finished } = byWork(rows)
    expect(active.map((work) => [work.mediaId, work.rows.map((row) => row.id)])).toEqual([
      ['tv:262000', [1, 3]],
      ['tv:1', [2]],
    ])
    expect(finished).toEqual([])
  })

  it('完結的收進另一份；同一部作品一組完結一組還在追時兩邊各一塊', () => {
    const rows = [
      series({ id: 1, finished: true }),
      series({ id: 3 }),
      series({ id: 4, media_id: 'tv:1', finished: true }),
    ]
    const { active, finished } = byWork(rows)
    expect(active.map((work) => work.rows.map((row) => row.id))).toEqual([[3]])
    expect(finished.map((work) => work.rows.map((row) => row.id))).toEqual([[1], [4]])
  })

  it('待綁定的不在裡面', () => {
    expect(byWork([series({ media_id: null })])).toEqual({ active: [], finished: [] })
  })
})

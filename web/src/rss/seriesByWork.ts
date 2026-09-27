import type { TFunction } from 'i18next'

import type { RssSeries } from '../api/rss'
import { displayRound } from '../i18n/displayRound'

/**
 * RSS 頁以作品呈現 Series（M4 票 13，`.scratch/m4/rss-series-shape.md`）：作品一塊、字幕組一列；完結的
 * （`finished`，後端照現況算）另成一份，收進預設收起的「已完結」。
 */
export interface WorkGroup {
  mediaId: string
  /** 這部作品的第一列：作品名的兩輪從它讀。 */
  lead: RssSeries
  /** 這一塊的 Route，去重、照出現的順序（同一部作品的兩組多半入同一條）。 */
  routes: string[]
  rows: RssSeries[]
}

export function byWork(rows: RssSeries[]): { active: WorkGroup[]; finished: WorkGroup[] } {
  const bound = rows.filter((row) => row.media_id !== null)
  return {
    active: group(bound.filter((row) => !row.finished)),
    finished: group(bound.filter((row) => row.finished)),
  }
}

function group(rows: RssSeries[]): WorkGroup[] {
  const works = new Map<string, WorkGroup>()
  for (const row of rows) {
    const mediaId = row.media_id ?? ''
    const work = works.get(mediaId) ?? { mediaId, lead: row, routes: [], rows: [] }
    if (row.route_name && !work.routes.includes(row.route_name)) work.routes.push(row.route_name)
    work.rows.push(row)
    works.set(mediaId, work)
  }
  return [...works.values()]
}

/**
 * 從哪裡來：Mikan 說番組名（與字幕組名），**不說數字 id**——試跑時列上寫的「Mikan 3985 × 583」是內部編號。
 * 名字沒讀到就只說 Mikan（不為了顯示多打 Mikan，brief §15）；其他站說站名。`group: false` 是列上已經有字幕組
 * 那一格的時候。
 */
export function sourceLabel(
  t: TFunction,
  row: RssSeries,
  { group = true }: { group?: boolean } = {},
): string {
  if (row.mikan_bangumi_id === null) return row.source ? t(`rss.kind.${row.source}`) : '—'
  const bangumi = row.mikan_bangumi_name
  if (!bangumi) return t('rss.source.mikanBare')
  if (group && row.mikan_subgroup_name) {
    return t('rss.source.mikanGroup', { bangumi, group: row.mikan_subgroup_name })
  }
  return t('rss.source.mikan', { bangumi })
}

/** Mikan 的番組頁（錨點是那個字幕組）。id 只在網址裡，不當成字印出來。 */
export function mikanPage(row: RssSeries): string | null {
  if (row.mikan_bangumi_id === null) return null
  const anchor = row.mikan_subgroup_id !== null ? `#${row.mikan_subgroup_id}` : ''
  return `https://mikanani.me/Home/Bangumi/${row.mikan_bangumi_id}${anchor}`
}

/**
 * 字幕組：Mikan 番組頁上的名字優先，其次發佈名讀出的；都沒有是空字串（呼叫端決定退回什麼）。RSS 頁、作品頁的
 * RSS 訂閱與第一批那一句都用它：同一個 Series 兩處說法不同才是錯。
 */
export function groupName(row: RssSeries): string {
  return row.mikan_subgroup_name || row.group
}

/** 作品名（跟著 UI 語言）；兩輪都沒有時退回作品 id。 */
export function workTitle(language: string, row: RssSeries): string {
  return (
    displayRound(language, { 'zh-Hant': row.media_title, en: row.media_title_en }) ||
    (row.media_id ?? '')
  )
}

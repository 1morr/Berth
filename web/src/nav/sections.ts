import type { TFunction } from 'i18next'

import type { WaitingCounts } from '../api/waiting'

/**
 * 頁首一個導覽項管一個區塊（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）：區塊裡任一頁都算
 * 當前，連結本身只指向區塊的第一頁。帳號選單裡的那幾頁同一個道理，觸發鍵在它們上面畫成當前。
 *
 * **一個區塊的設定只在這裡一份**（票 07 / 09 的 code-review 留下、票 12 收）：頁首的 `SectionLink`
 * 與每一頁 `<h1>` 上方的 `SectionTabs` 都讀它。加一頁只改這裡（加上 `routes.tsx` 的那一條路由）。
 */

/** 區塊分頁連得到的頁面。`Link` 的 `to` 要的是字面型別，所以列在這裡。 */
export type SectionPage = '/review' | '/issues' | '/schedule' | '/schedule/tracking' | '/rss'

/** 一個分頁。 */
export interface SectionTab {
  to: SectionPage
  /** i18n key。 */
  label: 'nav.review' | 'nav.issues' | 'nav.schedule' | 'nav.tracking' | 'nav.subscriptions'
  /** 只有 admin 看得到（後端同時回 403）。 */
  adminOnly: boolean
  /** 帶哪一格件數（`GET /waiting`，只有 admin）；不帶是 `undefined`。 */
  count?: keyof WaitingCounts
}

/** 一個區塊：頁首的一項加上它的分頁列。頁首那一項連到第一個分頁、件數是各分頁件數的和。 */
export interface Section {
  /** i18n key：頁首那一項，也是分頁列 `<nav>` 的名字。 */
  label: 'nav.waiting' | 'nav.airing'
  /** 整個區塊只有 admin（頁首那一項也不畫）。 */
  adminOnly: boolean
  tabs: readonly [SectionTab, ...SectionTab[]]
}

/** 待處理：審核與 Issue 仍是兩頁（ADR-0006），共用一條分頁列。 */
export const WAITING: Section = {
  label: 'nav.waiting',
  adminOnly: true,
  tabs: [
    { to: '/review', label: 'nav.review', adminOnly: true, count: 'review' },
    { to: '/issues', label: 'nav.issues', adminOnly: true, count: 'issue' },
  ],
}

/**
 * 新番：時間表（每個人，M5.5 票 09）、追更（admin，票 12）、訂閱（原 RSS 頁，admin，帶待綁定的件數）。
 * 一般使用者只有一個分頁也照畫：區塊的形狀與管理員看到的一樣，少的那幾格是他進不去的頁。
 */
export const AIRING: Section = {
  label: 'nav.airing',
  adminOnly: false,
  tabs: [
    { to: '/schedule', label: 'nav.schedule', adminOnly: false },
    { to: '/schedule/tracking', label: 'nav.tracking', adminOnly: true },
    { to: '/rss', label: 'nav.subscriptions', adminOnly: true, count: 'rss' },
  ],
}

/** 帳號選單裡的頁面。 */
export const ACCOUNT_PAGES = ['/settings', '/health', '/weekly'] as const

/** 這個人看得到的分頁。 */
export function visibleTabs(section: Section, admin: boolean): SectionTab[] {
  return section.tabs.filter((tab) => admin || !tab.adminOnly)
}

/** 一個分頁的件數；不帶件數、讀不到（不是 admin、還沒回來）是 `undefined`。 */
export function tabCount(tab: SectionTab, counts: WaitingCounts | undefined): number | undefined {
  return tab.count && counts ? counts[tab.count] : undefined
}

/** 頁首那一項的件數：各分頁件數的和（待處理＝審核＋Issue、新番＝待綁定）。 */
export function sectionCount(
  section: Section,
  counts: WaitingCounts | undefined,
): number | undefined {
  if (!counts) return undefined
  return section.tabs.reduce((sum, tab) => sum + (tabCount(tab, counts) ?? 0), 0)
}

/** 區塊的每一頁（`inSection` 比對用）。 */
export function sectionPages(section: Section): SectionPage[] {
  return section.tabs.map((tab) => tab.to)
}

/** `pathname` 是不是 `pages` 裡某一頁或它底下的頁（`/weekly/12` 在 `/weekly` 底下）。 */
export function inSection(pathname: string, pages: readonly string[]): boolean {
  return pages.some((page) => pathname === page || pathname.startsWith(`${page}/`))
}

/** 帶件數的連結念成什麼（「待處理 3 件」）；0 件就是標籤本身。可存取名稱以看得到的標籤開頭（WCAG 2.5.3）。 */
export function countedName(t: TFunction, label: string, count: number | undefined): string {
  return count ? t('nav.counted', { label, count }) : label
}

import type { TFunction } from 'i18next'

/**
 * 頁首一個導覽項管一個區塊（M5.5 票 07，`.scratch/m5.5/navigation-shape.md`）：區塊裡任一頁都算
 * 當前，連結本身只指向區塊的第一頁。帳號選單裡的那幾頁同一個道理，觸發鍵在它們上面畫成當前。
 */

/** 待處理：審核與 Issue 仍是兩頁（ADR-0006），共用一條分頁列。 */
export const WAITING_PAGES = ['/review', '/issues'] as const

/** 新番：時間表（每個人，M5.5 票 09）與訂閱（原 RSS 頁，只有 admin）；票 12 加追更。 */
export const AIRING_PAGES = ['/schedule', '/rss'] as const

/** 帳號選單裡的頁面。 */
export const ACCOUNT_PAGES = ['/settings', '/health', '/weekly'] as const

/** `pathname` 是不是 `pages` 裡某一頁或它底下的頁（`/weekly/12` 在 `/weekly` 底下）。 */
export function inSection(pathname: string, pages: readonly string[]): boolean {
  return pages.some((page) => pathname === page || pathname.startsWith(`${page}/`))
}

/** 帶件數的連結念成什麼（「待處理 3 件」）；0 件就是標籤本身。可存取名稱以看得到的標籤開頭（WCAG 2.5.3）。 */
export function countedName(t: TFunction, label: string, count: number | undefined): string {
  return count ? t('nav.counted', { label, count }) : label
}

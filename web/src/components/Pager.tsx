import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/** 分頁鍵：Ghost 的外觀，但它們換網址，所以是連結。到頭的那一顆是同樣大小的一段字。 */
const PAGE_KEY = 'label inline-flex min-h-6 items-center border-2 px-3 py-1.5'
/** 按得到的那一顆的外觀。連結由呼叫端畫（每一頁的路由與網址參數不同），套上這一格。 */
export const PAGE_LINK = `${PAGE_KEY} border-rule text-ink hover:border-rule-strong`

/** 這一頁是第幾筆到第幾筆。`beyond` 是頁碼超過最後一頁（網址是手打的，或翻頁的當下清單變短了）。 */
export interface PageRange {
  first: number
  last: number
  total: number
  beyond: boolean
}

/**
 * `1–50 / 523` 加上一頁 / 下一頁（jellyfin-web 的分頁，媒體庫的牆先用，M4 票 04 下載列表跟著用）。
 * 看得見的是數字，聽得見的是帶單位的那一句（DESIGN.md 的區塊標題規則）：清單上方那一組給 `announce`，
 * 放進 `aria-live`，換頁時念得出來；單位（部、筆）是呼叫端的，所以句子由它給。
 *
 * 清單上下各一組時**兩個 landmark 名字不同**（`label`，M1.5 票 13）：地標清單裡兩個同名的「分頁」分不出
 * 哪個是哪個（WAI-ARIA landmark 的慣例：同一種出現兩次就各給一個名字）。
 */
export function Pager({
  page,
  size,
  total,
  label,
  announce,
  link,
}: {
  page: number
  size: number
  total: number
  label: string
  announce?: (range: PageRange) => string
  /** 到第 `to` 頁的連結，外觀用 `PAGE_LINK`。 */
  link: (to: number, children: string) => ReactNode
}) {
  const { t } = useTranslation()
  if (total === 0) return null
  const pages = Math.max(1, Math.ceil(total / size))
  const range: PageRange = {
    first: Math.min((page - 1) * size + 1, total),
    last: Math.min(page * size, total),
    total,
    beyond: page > pages,
  }

  return (
    <nav aria-label={label} className="flex flex-wrap items-center gap-2">
      <span aria-hidden="true" className="value text-xs text-ink-dim">
        {range.beyond ? `— / ${total}` : `${range.first}–${range.last} / ${total}`}
      </span>
      {announce && (
        <span aria-live="polite" className="sr-only">
          {announce(range)}
        </span>
      )}
      {(pages > 1 || page > 1) && (
        <>
          <PageKey to={page > 1 ? Math.min(page - 1, pages) : null} link={link}>
            {t('pager.previous')}
          </PageKey>
          <PageKey to={page < pages ? page + 1 : null} link={link}>
            {t('pager.next')}
          </PageKey>
        </>
      )}
    </nav>
  )
}

function PageKey({
  to,
  link,
  children,
}: {
  to: number | null
  link: (to: number, children: string) => ReactNode
  children: string
}) {
  // 到頭了：位置不變、不是連結，說得出它按不了。
  if (to === null) {
    return (
      <span aria-disabled="true" className={`${PAGE_KEY} border-rule text-ink-dim`}>
        {children}
      </span>
    )
  }
  return link(to, children)
}

import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

/**
 * 結果卡共用的框（DESIGN.md〈助理側面板〉的結果卡）：`border-2 border-rule`，`deck` 抬頭列放 `.label` 的
 * `h3` 與 `.value text-xs` 的計數，內距小一號（卡片已經在助理那一塊的內距裡，面板只有 26rem）。
 */
export function CardFrame({
  labelId,
  heading,
  count,
  children,
}: {
  labelId: string
  heading: string
  count?: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-labelledby={labelId} className="border-2 border-rule">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule bg-deck px-3 py-2">
        <h3 id={labelId} className="label mr-auto text-ink">
          {heading}
        </h3>
        {count !== undefined && <p className="value text-xs text-ink-dim">{count}</p>}
      </div>
      {children}
    </section>
  )
}

/** 作品名連到作品頁。路徑由 `berthPages.test.ts` 對著後端的 `BerthPage.MEDIA`（M5 票 02）。 */
export function WorkLink({ media, children }: { media: string; children: ReactNode }) {
  return (
    <Link
      to="/media/$mediaId"
      params={{ mediaId: media }}
      className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
    >
      {children}
    </Link>
  )
}

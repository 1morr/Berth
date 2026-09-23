import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Notice } from './controls'
import { Dot } from './Dot'

/**
 * 工作清單上的一列：`/review` 的每一類、`/issues`，以及票 14 媒體庫的「待審 / 對不到」
 * （`.scratch/m2/review-shape.md`）。
 *
 * 票 05 刻意不抽它，等手上有兩個真實案例（`IssueRow`、`AuditRow`）——用一個案例猜介面會猜錯。
 * 共用的是這四格，由上到下（`PlanRow` 在第 2、3 格之間多一塊 `body`）：
 *
 * 1. **識別**：中性色塊的類別標籤＋標題。**不塗信號色**：清單上每一列都「在等人」，塗漆不區分
 *    任何東西（The Role Is Not A State Rule）；不看顏色也讀得出來靠的是那幾個模板字。
 * 2. **一句話**：理由翻成的句子，接「多久以前」。
 * 3. **展開**：機器字串收在 `<details>` 裡——掃視時不該被路徑淹沒，要修的時候才需要它們。
 * 4. **動作**：失敗時這一列留著，就地多一行為什麼。
 *
 * 這一列**不知道自己在哪一段**：`/review` 分三段，媒體庫的子集不分段，段落是頁面的事。
 * 標題層級因此由呼叫端給（分段底下是 `h3`，不分段是 `h2`）。
 */
export function QueueRow({
  label,
  title,
  heading = 'h2',
  sentence,
  when,
  body,
  details,
  refusal,
  children,
}: {
  label: string
  title: ReactNode
  heading?: 'h2' | 'h3'
  sentence: string
  /** 已經翻好的「偵測於 / 入庫於 …」。 */
  when: string
  /**
   * 這一列的工作本身，**不收在展開裡**：Plan 那一類的逐列表格（M2 票 07）——那張表就是要人做的事，
   * 收起來等於多一次點擊。其餘幾類沒有。
   */
  body?: ReactNode
  details: ReactNode
  refusal: string | null
  /** 動作列。順序照後端給的 `actions`。 */
  children: ReactNode
}) {
  const { t } = useTranslation()
  const Heading = heading

  return (
    <article className="grid gap-2 border-2 border-rule bg-well px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-2 py-1.5 text-ink">{label}</span>
        <Heading className="value min-w-0 wrap-anywhere text-ink">{title}</Heading>
      </div>

      <p className="text-sm text-ink-dim">
        {sentence}
        <Dot />
        <span className="value text-xs">{when}</span>
      </p>

      {body}

      <details className="group">
        <summary className="label w-fit cursor-pointer text-ink-dim hover:text-ink">
          {t('common.expand')}
        </summary>
        <dl className="mt-2 grid gap-1 border-2 border-rule bg-hull px-3 py-2">{details}</dl>
      </details>

      {refusal !== null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal}
        </Notice>
      )}

      <div className="flex flex-wrap items-start gap-2">{children}</div>
    </article>
  )
}

/** 展開區的一格：欄名走 `.label`，值走 `.value`——路徑與 hash 是機器字串（The Machine String Rule）。 */
export function DetailLine({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-2">
      <dt className="label text-ink-dim">{term}</dt>
      <dd className="value min-w-0 wrap-anywhere text-xs text-ink">{children}</dd>
    </div>
  )
}

import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Notice } from './controls'
import { Dot } from './Dot'
import { ExpandHint } from './ExpandHint'

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
 * 這一列**不知道自己在哪一段**：`/review` 分兩段，媒體庫的子集不分段，段落是頁面的事。
 * 標題層級因此由呼叫端給（分段底下是 `h3`，不分段是 `h2`，一組裡的成員是 `h4`）。
 *
 * **一組**（同一個 Job 的 audit，M3 票 05）也是一列：成員收在展開裡（`members`），一句話說整組；
 * 成員的那一句與組說的相同時就不再說（`sentence` 省略，只剩時間）。
 */
export function QueueRow({
  label,
  title,
  heading = 'h2',
  sentence,
  when,
  body,
  details,
  members,
  refusal,
  children,
}: {
  label: string
  title: ReactNode
  heading?: 'h2' | 'h3' | 'h4'
  /** 省略時只剩時間：上面那一組已經說過了（DESIGN.md 逐檔列「上面的摘要說過的，這一列不再說」）。 */
  sentence?: string
  /** 已經翻好的「偵測於 / 入庫於 …」。 */
  when: string
  /**
   * 這一列的工作本身，**不收在展開裡**：Plan 那一類的逐列表格（M2 票 07）、對不到那一類的修正表單
   * （票 08）——那就是要人做的事，收起來等於多一次點擊。其餘幾類沒有。
   */
  body?: ReactNode
  details: ReactNode
  /** 一組的成員，展開時接在 `details` 那張表之後。 */
  members?: ReactNode
  refusal: string | null
  /** 動作列。順序照後端給的 `actions`。工作本身就是表單（`body`）的那一類沒有另外的動作列。 */
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const Heading = heading
  const headingId = useId()
  // 「展開 / 收起」照這一列自己的開合，不用 `group-open:`：一組的成員長在組的 `<details>` 裡，
  // CSS 那一種會跟著外面那一層一起說「收起」（同 `CollapsibleRow`）。
  const [open, setOpen] = useState(false)

  return (
    // `tabIndex={-1}`：按完上一列、那一列消失時焦點落在這一列（`useFocusAfterRemoval`），`aria-labelledby` 讓螢幕
    // 閱讀器那時念得出是哪一件。
    <article
      tabIndex={-1}
      aria-labelledby={headingId}
      className="grid gap-2 border-2 border-rule bg-well px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-2 py-1.5 text-ink">{label}</span>
        <Heading id={headingId} className="value min-w-0 wrap-anywhere text-ink">
          {title}
        </Heading>
      </div>

      <p className="text-sm text-ink-dim">
        {/* `Dot` 在這裡是行內字，前後的空白要自己給——JSX 換行會把它吞掉（M2 票 16 的 audit：「…集·偵測於」）。 */}
        {sentence !== undefined && (
          <>
            {sentence} <Dot />{' '}
          </>
        )}
        <span className="value text-xs">{when}</span>
      </p>

      {body}

      <details onToggle={(event) => setOpen(event.currentTarget.open)}>
        {/* marker 拿掉、字跟著開合換（DESIGN.md 的 The Summary Is One Button Rule，同其他可展開列）：原本留著原生
            ▸ 又寫著「展開」，打開之後仍然說「展開」（M2 票 16 的 critique）。 */}
        <summary className="w-fit cursor-pointer marker:content-none">
          <ExpandHint open={open} />
        </summary>
        <dl className="mt-2 grid gap-1 border-2 border-rule bg-hull px-3 py-2">{details}</dl>
        {members}
      </details>

      {refusal !== null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal}
        </Notice>
      )}

      {children && <div className="flex flex-wrap items-start gap-2">{children}</div>}
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

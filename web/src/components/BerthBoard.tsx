import { useId, useState, type ReactNode } from 'react'

import { SIGNAL_FILL, type Signal } from './signal'

/**
 * 泊位板橫幅：等寬塗裝色塊（direction contract 的 FIRST VIEWPORT）。
 *
 * 狀態三重編碼——色塊 + 模板字標籤 + 泊位號，不看顏色也讀得出來。格子裡的每個字都是資訊。
 *
 * **精靈與健康頁是同一塊板**：那五個泊位（Jellyfin / qBittorrent / 媒體庫路徑 / 索引站 / TMDB）
 * 是同一組東西，精靈問「接上了沒」，健康頁問「還繫著嗎」。所以這裡只有版面，一格裡要
 * 寫什麼由呼叫端決定。
 */

export interface BoardSlot {
  /** 泊位識別碼（`BERTHS` 的 `code`）。 */
  code: string
  /** 已經翻譯好的服務名。 */
  name: string
  /** 已經翻譯好的狀態標籤（判定或信號）。 */
  status: string
  /** 實測值那一行。沒有值時留一條破折號，每一格的高度才不會跳。 */
  detail?: ReactNode
  signal: Signal
  /** 塗上色塊，還是留在中性底色上（還沒有任何結果的格子）。 */
  filled?: boolean
  /** 點得到（精靈上走過的與目前的那一格）。沒有 `onSelect` 的板上沒有意義。 */
  selectable?: boolean
}

/** 窄版摘要列上的字（已翻譯）。 */
export interface BoardSummaryWords {
  expand: string
  collapse: string
  /** 「阻擋」：摘要列用文字說出哪幾格紅了，不只靠小色塊的顏色。 */
  blocked: string
}

export function BerthBoard({
  label,
  slots,
  current,
  summary,
  onSelect,
}: {
  label: string
  slots: readonly BoardSlot[]
  /** 現在停在哪一格的 `code`。精靈才有；健康頁每一格同時成立，沒有「目前」。 */
  current?: string
  /**
   * 窄版（< 640px）收成一列摘要、按了才展開整塊板（M4 票 30，`.scratch/m4/wizard-navigation-shape.md`）：
   * 精靈的首屏要先看到這一頁要做的事。只有精靈給；健康頁的板就是那一頁的內容，照舊 2+2+1。
   */
  summary?: BoardSummaryWords
  /**
   * 點了哪一格（票 06d）。只有精靈給：走過的與目前的那幾格變成按鈕，還沒到的仍是純文字——
   * 前進只能靠把事做完。健康頁不給，整塊板沒有一個按鈕。
   */
  onSelect?: (code: string) => void
}) {
  const listId = useId()
  // 換了一頁就收起（shape：每次進頁收起、不記）。在 render 裡比上一次的那一格（React 的「props 變了就
  // 調整 state」）：只記「在哪一格展開的」的話，瀏覽器的上一頁回到那一格又是展開的（code-review）。
  const [open, setOpen] = useState(false)
  const [openedOn, setOpenedOn] = useState(current)
  if (openedOn !== current) {
    setOpenedOn(current)
    setOpen(false)
  }
  const folded = summary !== undefined && !open

  return (
    <section aria-label={label} className="border-b-2 border-rule-strong bg-hull">
      {summary && (
        <Summary
          label={label}
          slots={slots}
          current={current}
          words={summary}
          open={open}
          controls={listId}
          onToggle={() => setOpen(!open)}
        />
      )}
      {/* 窄版兩欄、桌機一列等寬（shape brief）。格數是奇數時最後一格橫跨整列，
          不留一個空洞（票 06d 的 shape：5 格在窄版排成 2+2+1，640 以上一列五格）。
          **不是** carousel：橫向捲動時後面幾格整個在畫面外，而「一眼看出哪一格
          紅了」正是這塊板存在的理由；捲動容器還會變成一個沒有名字的 Tab 停留點。
          欄數寫死：泊位就是那五個（`components/berths.ts`），而 Tailwind 看不見組出來的類名。
          精靈的窄版收起時不畫（`hidden sm:grid`）：一份 DOM 兩種版面，收起的板不進無障礙樹。 */}
      <ul
        id={listId}
        className={`${folded ? 'hidden sm:grid' : 'grid'} grid-cols-2 gap-px bg-rule-strong sm:grid-cols-5 [&>li:last-child:nth-child(odd)]:col-span-2 sm:[&>li:last-child:nth-child(odd)]:col-span-1`}
      >
        {slots.map((slot) => {
          const here = slot.code === current
          const paint = `${
            slot.filled === false ? 'bg-well text-ink-dim' : SIGNAL_FILL[slot.signal]
          } ${
            // 目前這一格的底線。用 currentColor 而不是第五個顏色——四個塗裝色上的
            // 字色本來就是為了在那塊漆上讀得出來而選的。inset 陰影不佔版面，格子不會跳。
            here ? 'shadow-[inset_0_-3px_0_0_currentColor]' : ''
          }`
          const body = <Cell slot={slot} />
          const selectable = onSelect !== undefined && slot.selectable === true

          return selectable ? (
            <li key={slot.code} className="flex">
              <button
                type="button"
                aria-current={here ? 'step' : undefined}
                onClick={() => onSelect(slot.code)}
                // hover 是線變重（DESIGN.md 的 The Heavier Line Rule），不是調亮度；
                // 內框用 outline，不跟目前那一格的 inset 底線搶同一個 box-shadow。
                className={`w-full min-w-0 cursor-pointer px-4 py-3 text-left ${paint} hover:outline-2 hover:-outline-offset-4 hover:outline-current`}
              >
                {body}
              </button>
            </li>
          ) : (
            <li
              key={slot.code}
              aria-current={here ? 'step' : undefined}
              className={`min-w-0 px-4 py-3 ${paint}`}
            >
              {body}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * 窄版的那一列摘要（M4 票 30）：整列是一顆展開鍵。五個帶泊位號的小色塊讓「哪一格紅了」仍然一眼看得出
 * （板存在的理由），目前那一格加同一條底線；字說出目前那一格與它的狀態，紅了的其他格另用字列出——
 * 小色塊只有顏色與號碼，不看顏色的人讀的是這一行。完成頁沒有目前那一格，就說板的名字。
 */
function Summary({
  label,
  slots,
  current,
  words,
  open,
  controls,
  onToggle,
}: {
  label: string
  slots: readonly BoardSlot[]
  current: string | undefined
  words: BoardSummaryWords
  open: boolean
  controls: string
  onToggle: () => void
}) {
  const here = slots.find((slot) => slot.code === current)
  const blocked = slots.filter((slot) => slot.signal === 'blocked' && slot !== here)

  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className={`flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left hover:outline-2 hover:-outline-offset-4 hover:outline-rule-strong sm:hidden ${
        open ? 'border-b-2 border-rule' : ''
      }`}
    >
      <span aria-hidden className="flex shrink-0 gap-px bg-rule-strong p-px">
        {slots.map((slot) => (
          <span
            key={slot.code}
            className={`value grid size-6 place-items-center text-xs font-semibold ${
              slot.filled === false ? 'bg-well text-ink-dim' : SIGNAL_FILL[slot.signal]
            } ${slot === here ? 'shadow-[inset_0_-3px_0_0_currentColor]' : ''}`}
          >
            {slot.code.replace(/\D+/g, '')}
          </span>
        ))}
      </span>
      <span className="min-w-0 flex-1">
        {here ? (
          <span className="flex flex-wrap items-baseline gap-x-2">
            <span className="value text-xs font-semibold">{here.code}</span>
            <span className="value truncate text-sm font-semibold">{here.name}</span>
            <span className="label text-ink-dim">{here.status}</span>
          </span>
        ) : (
          <span className="label text-ink-dim">{label}</span>
        )}
        {blocked.length > 0 && (
          <span className="label mt-1 block text-blocked-ink">
            {words.blocked} {blocked.map((slot) => slot.code).join(' · ')}
          </span>
        )}
      </span>
      <span className="label shrink-0 text-ink-dim">
        {open ? words.collapse : words.expand}
        <span aria-hidden> {open ? '▴' : '▾'}</span>
      </span>
    </button>
  )
}

function Cell({ slot }: { slot: BoardSlot }) {
  // 次要字在漆上退一階。沒塗漆的格子字本來就是 `ink-dim`，再淡一層在淺色主題只剩 3.73:1
  // （票 06h 的 audit，WCAG 1.4.3），所以只對塗了漆的格子退。
  const secondary = slot.filled === false ? '' : 'opacity-80'
  return (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="value text-xs font-semibold">{slot.code}</span>
        <span className={`label ${secondary}`}>{slot.status}</span>
      </div>
      <p className="value mt-2 truncate text-base font-semibold">{slot.name}</p>
      {/* 不截斷（DESIGN.md）：390 寬時版本那一行會比格子寬，換行而不是吃掉後半（票 15 的 audit）。 */}
      <p className={`value mt-1 min-h-4 text-xs wrap-anywhere ${secondary}`}>
        {slot.detail || '—'}
      </p>
    </>
  )
}

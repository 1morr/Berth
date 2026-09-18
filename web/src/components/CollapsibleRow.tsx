import { useRef, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { COMPACT_BUTTON } from './controls'
import { ExpandHint } from './ExpandHint'

/**
 * 長清單的一段（`.scratch/m1.5/long-lists-shape.md` §3）：季表的一季、檔案與版本的一組、計劃的一組。
 *
 * 三件事一起給，三處才不會各做一半（使用者 2026-09-18 拍板）：
 *
 * - **收起時不渲染內容**：`children` 是函式，展開才呼叫。一季 1213 集的表收起時仍在 DOM 裡，開頁就多上萬個節點
 *   （票 15 audit）。代價是瀏覽器的頁內搜尋找不到收起的內容。
 * - **展開時摘要列黏在畫面頂端**（GitHub PR「Files changed」的檔案標頭）：捲到這一段的任何位置都按得到收起。
 * - **內容最後一行「收起 X」**：從底端收起時焦點回到摘要列。兩條路收起之後，摘要列若在畫面上方就捲回來——
 *   不讓人落在下一段的中間。
 *
 * 原生 `<details>`（DESIGN.md：原生優先，全域焦點環已涵蓋 `summary`），`<summary>` 裡只放字（The Summary Is One
 * Button Rule）。「展開 / 收起」把狀態交給 `ExpandHint`，**不用它的 `group-open:` 那一種**：下載列本身是一個帶
 * `group` 的 `<details>`，計劃的一組長在它裡面，`group-open:` 會跟著外面那一層亮。
 */
export function CollapsibleRow({
  name,
  summary,
  held = false,
  children,
}: {
  /** 底端那一顆說的是收起哪一段：`S01`、`正片 S01 E01–E28`。 */
  name: string
  summary: ReactNode
  /** 需要人的那一組：左線 `rule-strong`（The Needs-You Floats Up Rule；線變重，不是變紅）。 */
  held?: boolean
  children: () => ReactNode
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const head = useRef<HTMLElement>(null)

  function bringBack() {
    const element = head.current
    if (element && element.getBoundingClientRect().top < 0)
      element.scrollIntoView({ block: 'start' })
  }

  // `flushSync`：要在收起**之後**才量得到摘要列的新位置、把焦點送回它身上，而 `setOpen` 自己是非同步的。
  function collapse() {
    flushSync(() => setOpen(false))
    bringBack()
    head.current?.focus({ preventScroll: true })
  }

  return (
    <details
      open={open}
      onToggle={(event) => {
        const next = event.currentTarget.open
        setOpen(next)
        if (!next) bringBack()
      }}
      // `min-w-0`：grid 項目的 `min-width` 預設是 `auto`，展開的集表曾把整頁撐到 560px（DESIGN.md 手機一節）。
      className={`min-w-0 border-l-2 bg-well ${held ? 'border-rule-strong' : 'border-transparent'}`}
    >
      <summary
        ref={head}
        // `bg-well` 不能拿掉：黏頂時底下的內容從它下面捲過去。
        className={`sticky top-0 z-10 flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 bg-well px-4 py-3 marker:content-none ${
          open ? 'border-b-2 border-rule' : ''
        }`}
      >
        {summary}
        <ExpandHint open={open} className="ml-auto" />
      </summary>
      {open && (
        // 反向 Tab 回到這一段裡的連結時，瀏覽器會把它捲到畫面頂端——那裡是黏頂的摘要列。`scroll-margin` 讓它停在
        // 摘要列下面（WCAG 2.2 2.4.11；窄版摘要列約 90px）。
        <div className="grid bg-hull [&_:is(a,button)]:scroll-mt-32 [&>*]:min-w-0">
          {children()}
          <p className="border-t-2 border-rule px-4 py-2">
            <button type="button" onClick={collapse} className={COMPACT_BUTTON}>
              {t('common.collapseNamed', { name })}
            </button>
          </p>
        </div>
      )}
    </details>
  )
}

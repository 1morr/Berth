import { useState, type ReactNode } from 'react'

import { ExpandHint } from './ExpandHint'

/**
 * 一份逐檔清單裡的一筆：**摘要一行，長的那幾段收在裡面**（M1.5 票 09b）。
 *
 * 票 09 把「檔案與版本」與計劃收成分組，但逐檔那一列沿用了原本的樣子，所以展開一組之後一個檔案
 * 仍然三到四行（芙莉蓮 28 個檔案 2,775px）。這一份把它收成一行：留在外面的是**認得出這一筆、而且
 * 要拿來掃的**那幾格，收起來的是會換行三次的路徑與一個檔案好幾條的理由。
 *
 * **組的摘要說過的不再重複**：呼叫端自己決定留哪幾格——計劃那一份的處置、信心與待確認是組鍵的一部分
 * （一組裡必然相同），帳本「對得上」與 Jellyfin「已收錄」則由組的計數說。只有組說不出口的才留在列上
 * （帳本對不上是哪一個、還在掃描的下一次什麼時候查、反查試了幾次）。
 *
 * **內容留在 DOM 裡**（不像 `CollapsibleRow` 收起時不渲染）：一筆檔案裡面只有兩三行，而這一整份清單
 * 本身已經收在組裡了——真正會多出一萬個節點的是 1213 集那張表，不是這裡。留著的好處是組展開之後
 * 瀏覽器的頁內搜尋仍然找得到路徑。
 *
 * **提示一定要走 `ExpandHint` 的受控 `open`**：`group-open:` 匹配的是任一個帶 `group` 的祖先而不是最近的
 * 那一個，而這一列長在下載列那一筆（`JobRow` 帶 `group`）裡面——用 CSS 那一種，外層一展開每一列都會說
 * 「收起」。票 09 已經為了組長列踩過同一個坑。
 *
 * `heavy` 是「這一列要人看一眼」：**線變重，不是變紅**（The One Meaning Rule）。
 */
export function FileEntry({
  heavy = false,
  summary,
  children,
}: {
  heavy?: boolean
  summary: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)

  return (
    // `min-w-0`：grid 項目預設不肯縮，長路徑會把整頁撐寬（票 04 踩過的同一個坑）。
    <li className={`min-w-0 border-l-2 pl-3 ${heavy ? 'border-rule-strong' : 'border-rule'}`}>
      <details
        open={open}
        onToggle={(event) => setOpen(event.currentTarget.open)}
        className="min-w-0"
      >
        <summary className="flex cursor-pointer flex-wrap items-center gap-x-2 gap-y-1 marker:content-none">
          {summary}
          <ExpandHint open={open} className="ml-auto" />
        </summary>
        <div className="grid min-w-0 gap-1 pt-1">{children}</div>
      </details>
    </li>
  )
}

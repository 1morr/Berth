import { useEffect, useEffectEvent, useState } from 'react'

import type { BundledLibrary, JellyfinSetup, LibraryDraft } from '../api/setup'
import { folderFor, hasProblems, problemsOf, type ListProblems } from './libraryRules'

/** 剖面上的一列。`key` 只給 React 認列；`folderEdited` 之前資料夾跟著名稱推導。 */
export interface DraftRow extends LibraryDraft {
  key: number
  built: boolean
  folderEdited: boolean
}

/** 停手多久才存。每個按鍵存一次沒有必要，但關掉分頁之前要來得及存到。 */
export const SAVE_DEBOUNCE_MS = 600

function fromServer(rows: readonly BundledLibrary[]): DraftRow[] {
  return rows.map((row, index) => ({
    key: index,
    name: row.name,
    collection_type: row.collection_type,
    folder: row.folder,
    built: row.built,
    // 存下來的資料夾不是推導出來的那一個，就是使用者自己填過的：改名時不要蓋掉它。
    folderEdited: row.folder !== folderFor(row.name),
  }))
}

function toDraft(row: LibraryDraft): LibraryDraft {
  return { name: row.name.trim(), collection_type: row.collection_type, folder: row.folder.trim() }
}

export interface LibraryDraftState {
  rows: DraftRow[]
  setRows: (rows: DraftRow[]) => void
  /** 要送出的那一份：修掉前後空白，與後端存下來的形狀一樣。 */
  drafts: LibraryDraft[]
  problems: ListProblems
  /** 有問題就不存也不讓靠泊。 */
  blocked: boolean
}

/**
 * 剖面的草稿，與存下來的那一份同步：沒有問題、又與存下來的不一樣時，停手一會兒就存
 * （關掉瀏覽器回來還在，plan §9.3「續行」）。
 *
 * **建好的那幾列變了就從伺服器重來一次**：靠泊之後「已建立」要鎖上，而那時草稿與伺服器的
 * 內容本來就一樣（按之前先存過）。只看建好的名字，所以輪詢進度與存檔的回應不會打斷正在打的字。
 */
export function useLibraryDraft(
  setup: JellyfinSetup,
  save: (drafts: LibraryDraft[]) => void,
): LibraryDraftState {
  const built = setup.bundled
    .filter((row) => row.built)
    .map((row) => row.name)
    .join('\n')
  const [rows, setRows] = useState(() => fromServer(setup.bundled))
  const [seen, setSeen] = useState(built)
  if (seen !== built) {
    setSeen(built)
    setRows(fromServer(setup.bundled))
  }

  const drafts = rows.map(toDraft)
  const problems = problemsOf(drafts)
  const blocked = hasProblems(problems)
  const pending = JSON.stringify(drafts)
  const stored = JSON.stringify(setup.bundled.map(toDraft))
  const persist = useEffectEvent(() => save(drafts))

  useEffect(() => {
    if (blocked || pending === stored) return
    const timer = setTimeout(persist, SAVE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [blocked, pending, stored])

  return { rows, setRows, drafts, problems, blocked }
}

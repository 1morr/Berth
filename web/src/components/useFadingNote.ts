import { useEffect, useState } from 'react'

/** 「已刪除」這類完成通知在畫面上留多久。夠念完、夠看一眼，之後不再冒充現況。 */
export const NOTE_MS = 8000

/**
 * 做完之後說一聲、過一會兒自己收掉的那一句（M4 票 21）：刪掉 Route 之後的「已刪除 X」原本一直掛著，
 * 再建一條、再檢查一次都還在，看起來像剛剛又發生了一次。
 *
 * 留在一直都在的 `aria-live` 區塊裡寫（呼叫端的 `<p aria-live>`），螢幕閱讀器照樣念得到；清掉是換成空字串，
 * 不是卸下那個區塊。
 */
export function useFadingNote(ms = NOTE_MS): [string, (note: string) => void] {
  // 帶一個序號：連著說兩次同一句（連刪兩條同名的 Route）時計時器也要重新起算。
  const [note, setNote] = useState({ text: '', serial: 0 })

  useEffect(() => {
    if (!note.text) return
    const timer = window.setTimeout(() => setNote((was) => ({ ...was, text: '' })), ms)
    return () => window.clearTimeout(timer)
  }, [note, ms])

  return [note.text, (text) => setNote((was) => ({ text, serial: was.serial + 1 }))]
}

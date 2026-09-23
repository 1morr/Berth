import type { Watching } from '../api/watching'

/** 繼續觀看與下一集上一次兩列各有幾格。 */
export interface RowShape {
  resume: number
  nextUp: number
}

const PREFIX = 'berth.watching.'

/**
 * 繼續觀看與下一集讀取中要佔多少位（M2 票 13，使用者拍板）：照**這個人在這一頁上一次看到的形狀**。
 *
 * 讀完之前不知道會是零、一還是兩列，任何固定的佔位都只對其中一種剛好——佔多了，資料到的時候下方整頁往上收，
 * 那一樣是版面位移（首頁量到 CLS 0.35）。上一次的形狀多數時候就是這一次的，只有列數變了（剛看完一部、剛開始
 * 看一部）的那一次會動。第一次來沒有紀錄，不佔位，與 M1.5 的做法相同。
 *
 * 存在 `localStorage`：這是「這台瀏覽器上的一點方便」，不是要可靠保存的狀態。讀寫都可能丟例外（隱私模式、
 * 封鎖網站資料），丟了就當沒有紀錄。`key` 帶著使用者與頁面（首頁或哪一個媒體庫）。
 */
export function rememberedRows(key: string): RowShape | null {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(PREFIX + key) ?? 'null')
    return isShape(stored) ? stored : null
  } catch {
    return null
  }
}

export function rememberRows(key: string, watching: Watching): void {
  const shape: RowShape = { resume: watching.resume.length, nextUp: watching.next_up.length }
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(shape))
  } catch {
    // 存不下來只是下一次讀取中不佔位。
  }
}

function isShape(value: unknown): value is RowShape {
  if (typeof value !== 'object' || value === null) return false
  const { resume, nextUp } = value as Record<string, unknown>
  return isCount(resume) && isCount(nextUp)
}

function isCount(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= 0
}

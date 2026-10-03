/**
 * Jellyfin 帳號的修剪與規則（M4 票 29）。規則照 Jellyfin 12.1 的 `UserManager`（brief §20.7）：
 * `ValidUsernameRegex` 是 `^(?!\s)[\w\ \-'._@+]+(?<!\s)$`，另外不收 `.` 與 `..`；建立管理員
 * （`POST /Startup/User`）違規時回 400，畫面原本只能說「那一段沒做完」（實測 B2-05～07）。
 */

/**
 * 送出前的帳號：前後的空白不算。頁 1 與登入頁用同一支（實測 B2-15：頁 1 修剪、登入頁不修剪）。
 * Jellyfin 的帳號前後本來就不能是空白，修掉不會讓任何一個合法帳號登不進去。
 */
export function trimUsername(raw: string): string {
  return raw.trim()
}

/**
 * .NET 的 `\w` 是 `[\p{L}\p{Mn}\p{Nd}\p{Pc}]`；再加上空格與 `-'._@+`。前後的空白由修剪處理，
 * 所以 regex 裡的兩個 lookaround 在這裡不必寫。
 */
const ALLOWED = /^[\p{L}\p{Mn}\p{Nd}\p{Pc} \-'.@+]+$/u

export type UsernameProblem = 'blank' | 'characters'

/** 建立 Jellyfin 帳號時這個名字哪裡不行；可以就是 `null`。看的是修剪之後的。 */
export function usernameProblem(raw: string): UsernameProblem | null {
  const name = trimUsername(raw)
  if (!name) return 'blank'
  if (!ALLOWED.test(name) || name === '.' || name === '..') return 'characters'
  return null
}

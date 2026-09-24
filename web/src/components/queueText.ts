/** 工作清單的列（`QueueRow`）共用的兩個字串整理。與元件分檔：Fast Refresh 只認純元件檔。 */

/** `/a/b/c.mkv` → `c.mkv`。路徑是 POSIX 的（帳本記的那一串，`models/ledger.py`）。 */
export function fileName(path: string) {
  const parts = path.split(/[\\/]/)
  return parts[parts.length - 1] ?? ''
}

/**
 * 絕對時間，照 **UI 的語言**（`i18n.language`，同 `Timestamp`）而不是瀏覽器的——後者讓 EN 介面印出
 * 「上午10:31:36」。認不得的原樣印出：它仍然是後端說的那一個值。
 */
export function whenText(value: string, language: string) {
  const at = new Date(value)
  return Number.isNaN(at.getTime()) ? value : at.toLocaleString(language)
}

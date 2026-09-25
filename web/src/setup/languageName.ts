/**
 * 索引站的語言代碼 → 照 UI 語言的語言名（票 06e）：`zh-TW` 在中文介面是「中文（台灣）」、
 * 在英文介面是「Chinese (Taiwan)」。代碼是 Prowlarr 定義自帶的 BCP 47，用 `Intl.DisplayNames`
 * 換，不自己維護一張表。認不得的代碼原樣顯示——說不出名字也比什麼都不說好。
 */
export function languageName(code: string, uiLanguage: string): string {
  if (!code) return ''
  try {
    return new Intl.DisplayNames([uiLanguage], { type: 'language' }).of(code) ?? code
  } catch {
    // 形狀不對的代碼（`RangeError`）：原樣。
    return code
  }
}

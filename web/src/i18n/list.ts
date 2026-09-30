/**
 * 一串名字接成一句（「Movies、TV、Anime」）。英文照 `Intl.ListFormat`（Oxford comma、and）；
 * 中文不用它：`zh-Hant` 的最後一個接成「和」而且不留空格，名字是英文時變成「Movies、TV和Anime」
 * （M4 票 21 的小瑕疵）。全用頓號，中英混排都讀得通。
 */
export function formatList(names: readonly string[], language: string): string {
  if (language.startsWith('zh')) return names.join('、')
  return new Intl.ListFormat(language).format(names)
}

/**
 * 一串名字接成一句（「Movies、TV、Anime」）。英文照 `Intl.ListFormat`（Oxford comma、and）；
 * 中文不用它：`zh-Hant` 的最後一個接成「和」而且不留空格，名字是英文時變成「Movies、TV和Anime」
 * （M4 票 21 的小瑕疵）。全用頓號，中英混排都讀得通。
 */
export function formatList(names: readonly string[], language: string): string {
  if (language.startsWith('zh')) return names.join('、')
  return new Intl.ListFormat(language).format(names)
}

/**
 * 兩句接在一起時中間放什麼：中文句號之後不留空白（「…訂閱。卡住的…」），英文留一格（M5.5 票 19 的
 * code-review：用 `{' '}` 接中文句會多一個空白）。
 */
export function sentenceGap(language: string): string {
  return language.startsWith('zh') ? '' : ' '
}

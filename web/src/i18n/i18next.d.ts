import type { resources } from './resources'

// 讓 t() 的 key 變成型別檢查得到的東西：打錯或刪掉的 key 會是編譯錯誤。
// `strictKeyChecks` 預設是 false——沒有它，認不得的 key 只會在畫面上原樣印出來，
// 編譯完全不吭聲（票 06 踩到：`en` 有而 `zh-Hant` 沒有的 key 一路通過 tsc）。
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    strictKeyChecks: true
    resources: (typeof resources)['zh-Hant']
  }
}

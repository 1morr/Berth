import type { resources } from './resources'

// 讓 t() 的 key 變成型別檢查得到的東西：打錯或刪掉的 key 會是編譯錯誤。
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: (typeof resources)['zh-Hant']
  }
}

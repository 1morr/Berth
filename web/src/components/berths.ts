/**
 * 那四個泊位是誰。`code` 不走 i18n——ISO 6346 的貨櫃標識與船期表的泊位號在哪個語言都是
 * 同一串字母數字。第三格是「來源」而不是 Prowlarr：它也可能是任意 Torznab 端點。
 *
 * 精靈與健康頁共用這一份：兩邊講的是同一組泊位，各寫一份遲早會分岔。
 */
export const BERTHS = [
  { code: 'BTH 1', nameKey: 'board.jellyfin' },
  { code: 'BTH 2', nameKey: 'board.qbittorrent' },
  { code: 'BTH 3', nameKey: 'board.source' },
  { code: 'BTH 4', nameKey: 'board.library' },
] as const satisfies readonly { code: string; nameKey: string }[]

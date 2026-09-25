import type { ServiceKind } from '../api/schemas'

/**
 * 那四個泊位是誰。`code` 不走 i18n——ISO 6346 的貨櫃標識與船期表的泊位號在哪個語言都是
 * 同一串字母數字。第三格是「來源」而不是 Prowlarr：它也可能是任意 Torznab 端點。
 *
 * 精靈與健康頁共用這一份：兩邊講的是同一組泊位，各寫一份遲早會分岔——而這件事真的發生過
 * （票 11 的 code review：泊位順序一度散在四個檔案裡，號碼、代號、服務三種形狀各寫一份）。
 * 所以「哪一格是哪個服務」也放在這裡，其餘全部從它導出。
 */
export const BERTHS = [
  { code: 'BTH 1', nameKey: 'board.jellyfin', slot: 'jellyfin' },
  { code: 'BTH 2', nameKey: 'board.qbittorrent', slot: 'qbittorrent' },
  // 媒體庫路徑排在來源之前（票 06d）：它只依賴前兩格，掛載設錯的人越早知道越好。
  // 這一格沒有服務判定：它的狀態來自 Route 自己的跨服務檢查。
  { code: 'BTH 3', nameKey: 'board.library', slot: 'library' },
  { code: 'BTH 4', nameKey: 'board.source', slot: 'prowlarr' },
] as const satisfies readonly { code: string; nameKey: string; slot: BerthSlot }[]

/** 一格對到的東西：三個外部服務，或媒體庫路徑那一格的 Route。 */
export type BerthSlot = ServiceKind | 'library'

/**
 * 「來源」那一格對到的服務判定。它同時掛著 TMDB 閘門（plan §9.3 第 5、6 步是同一個泊位），
 * 所以呼叫端偶爾要認出這一格——認的是這個名字，不是散在各處的 `'prowlarr'` 字面值。
 */
export const SOURCE_SLOT: BerthSlot = 'prowlarr'

/** 服務 → 泊位號（1 起算，就是 `BTH n` 的 n）。 */
export function berthNumberOf(slot: BerthSlot): number {
  return BERTHS.findIndex((berth) => berth.slot === slot) + 1
}

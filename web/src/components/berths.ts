import type { ServiceKind } from '../api/schemas'

/**
 * 那五個泊位是誰。`code` 不走 i18n——ISO 6346 的貨櫃標識與船期表的泊位號在哪個語言都是
 * 同一串字母數字。
 *
 * **一格一個服務**（票 06e，使用者拍板）：原本的第四格「來源」同時掛著索引站與 TMDB，一格兩半，
 * 詳情列走到 TMDB 那一步就換掉索引站數。拆開之後每一格說的都只是它自己那個服務。
 * 索引站那一格的名字是「索引站」而不是 Prowlarr：它也可能是任意 Torznab 端點，實際是哪一種
 * 寫在詳情列上。
 *
 * 精靈與健康頁共用這一份：兩邊講的是同一組泊位，各寫一份遲早會分岔——而這件事真的發生過
 * （票 11 的 code review：泊位順序一度散在四個檔案裡，號碼、代號、服務三種形狀各寫一份）。
 * 所以「哪一格是哪個服務」也放在這裡，其餘全部從它導出。
 *
 * **設定頁一格一頁**（票 06i）：精靈只管第一次，跑完之後改東西在設定頁的那一頁。分頁列、
 * 健康頁與各處「去設定」的連結都從 `settings` 這一欄導出，所以分頁的順序就是板的順序。
 */
export const BERTHS = [
  { code: 'BTH 1', nameKey: 'board.jellyfin', slot: 'jellyfin', settings: '/settings/jellyfin' },
  {
    code: 'BTH 2',
    nameKey: 'board.qbittorrent',
    slot: 'qbittorrent',
    settings: '/settings/qbittorrent',
  },
  // 媒體庫路徑排在索引站之前（票 06d）：它只依賴前兩格，掛載設錯的人越早知道越好。
  // 這一格沒有服務判定：它的狀態來自 Route 自己的跨服務檢查。
  { code: 'BTH 3', nameKey: 'board.library', slot: 'library', settings: '/settings/routes' },
  { code: 'BTH 4', nameKey: 'board.indexers', slot: 'prowlarr', settings: '/settings/indexers' },
  // TMDB 也沒有服務判定（它不在 compose 裡）：狀態來自精靈第 7 步的憑證測試。
  { code: 'BTH 5', nameKey: 'board.tmdb', slot: 'tmdb', settings: '/settings/tmdb' },
] as const satisfies readonly {
  code: string
  nameKey: string
  slot: BerthSlot
  settings: `/settings/${string}`
}[]

/** 一格對到的東西：三個外部服務，或媒體庫路徑那一格的 Route，或 TMDB 的憑證。 */
export type BerthSlot = ServiceKind | 'library' | 'tmdb'

type Berth = (typeof BERTHS)[number]

/** 一格的那一列。每一種 `BerthSlot` 都在表上，找不到是這張表寫錯了。 */
export function berthOf(slot: BerthSlot): Berth {
  const berth = BERTHS.find((row) => row.slot === slot)
  if (!berth) throw new Error(`no berth for ${slot}`)
  return berth
}

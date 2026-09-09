import type { MediaKind } from '../api/schemas'

/**
 * 類型代號。**不走 i18n**：它與 `BTH 1` 同一個語域——分類代號在哪個語言都是同一串字母
 * （`.scratch/m1/discover-shape.md` §8）。也不走 `.label`，那會把拉丁字母大寫掉，
 * 而這兩個字串本來就是大寫的代號，套上去只是多一層會說謊的處理。
 *
 * 探索牆的卡片與 Media 詳情頁的識別欄位共用這一份——同一個代號各寫一份遲早會分岔。
 */
export const KIND_CODE = { tv: 'TV', movie: 'MOVIE' } as const satisfies Record<MediaKind, string>

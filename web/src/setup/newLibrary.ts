import type { LibraryChoice } from '../api/setup'
import { pathUnder, slugOf } from './libraryRules'

/**
 * 既有 Jellyfin 頁 3 的「新建一個媒體庫」那一列（M4 票 64，`.scratch/m4/existing-new-library-shape.md`）。
 *
 * 規則與後端 `services.jellyfin.check_new_libraries` 是同一組；後端那一份是閘門，這一份讓畫面在按之前
 * 就說得出哪裡撞了。前端多擋一種：同名的。後端把同名當成「已經建好了」略過（重按不長出「電影2」），
 * 但在這一列打出那台已有的名字，意思是要另一個，那就該說出來。
 */

export type NewLibraryType = 'movies' | 'tvshows'

export interface NewLibraryState {
  ticked: boolean
  /** `null` 是還沒選過：跟著 `missingType` 走。 */
  type: NewLibraryType | null
  /** `null` 是還沒改過：名稱跟著類型預填（`routes.newLibrary.defaultName`）。 */
  name: string | null
  /** 按下「建立並檢查」時送出去的名稱：它出現在 Jellyfin 的清單上，這一列就收回去。 */
  sent: string | null
}

/** 沒勾、跟著預設走的那一列。 */
export const UNTOUCHED: NewLibraryState = { ticked: false, type: null, name: null, sent: null }

export type NewLibraryProblem =
  | { reason: 'name_missing' }
  | { reason: 'name_taken'; holder: string }
  | { reason: 'folder_taken'; holder: string }

/** 新的媒體庫要放在那台還沒有的類型；兩種都有（或都沒有）時是電影。 */
export function missingType(libraries: readonly LibraryChoice[]): NewLibraryType {
  const has = (type: NewLibraryType) => libraries.some((row) => row.collection_type === type)
  return has('movies') && !has('tvshows') ? 'tvshows' : 'movies'
}

/** 媒體庫名 → 資料夾。後端 `library_slug` 的同一條規則，中日文照留（`slugOf`）；全被修掉時是 `berth`。 */
export function librarySlug(name: string): string {
  return slugOf(name) || 'berth'
}

/** 新建的那一個落在哪裡：`<library root>/<slug>`（後端 `bundled_path(library_slug(名稱))`）。 */
export function newLibraryPath(libraryRoot: string, name: string): string {
  return pathUnder(libraryRoot, librarySlug(name.trim()))
}

/**
 * 這一列能不能建。`claimed` 是這一輪勾選的媒體庫要加的新 Berth 路徑：撞到它的話兩個媒體庫會掃同一個
 * 資料夾，後端會讓後加的那一條失敗（`path_taken`）——在按之前就說。
 */
export function newLibraryProblem(
  name: string,
  path: string,
  libraries: readonly LibraryChoice[],
  claimed: readonly { library: string; path: string }[],
): NewLibraryProblem | null {
  const trimmed = name.trim()
  if (!trimmed) return { reason: 'name_missing' }
  const twin = libraries.find((row) => key(row.name) === key(trimmed))
  if (twin) return { reason: 'name_taken', holder: twin.name }
  const holder =
    libraries.find((row) => row.locations.includes(path))?.name ??
    claimed.find((row) => row.path === path)?.library
  return holder ? { reason: 'folder_taken', holder } : null
}

/** 不分大小寫（後端 `casefold`）。 */
function key(value: string): string {
  return value.toLocaleLowerCase('en')
}

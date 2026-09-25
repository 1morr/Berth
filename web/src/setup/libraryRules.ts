import type { BundledLibraryRefusal, LibraryDraft } from '../api/setup'

/**
 * 套件內 Jellyfin 的媒體庫清單（票 06f）：名稱推導資料夾，以及送出之前就擋下來的規則。
 *
 * 規則與後端 `services.jellyfin.check_bundled_libraries` 是同一組，兩邊各自有測試；後端那一份
 * 才是閘門，這一份讓剖面在按鍵之前就說得出是哪一格不行。後端一次只回第一個問題，這裡每一格
 * 各說各的。「已建好的那一列被改了」這裡不擋：那幾列在畫面上根本改不動。
 */

type NameProblem = Extract<BundledLibraryRefusal, 'name_missing' | 'name_taken'>
type FolderProblem = Extract<
  BundledLibraryRefusal,
  'folder_missing' | 'folder_taken' | 'folder_outside_root' | 'folder_characters'
>

export interface RowProblems {
  name?: NameProblem
  folder?: FolderProblem
}

export interface ListProblems {
  /** 一列都沒有。 */
  empty: boolean
  /** 與清單同序，每一列一格；沒問題的是 `{}`。 */
  rows: RowProblems[]
}

/** 有分隔符號、或整個是 `.` / `..`：跳出 `library_root`，或往下鑽成巢狀的媒體庫。 */
const OUTSIDE_ROOT = /[/\\]|^\.{1,2}$/
/** Windows 不收的字元（brief §4.5）。控制字元另外看碼位，免得正則裡寫控制字元。 */
const UNSAFE = /[<>:"|?*]/
/** 後端 `_UNSAFE_IN_PATH` 除了控制字元以外的那幾個，推導時換成 `-`。 */
const UNSAFE_IN_NAME = /[<>:"/\\|?*]+/g
const PRINTABLE_ASCII = /^[\x20-\x7e]*$/

/**
 * 名稱 → 預設的資料夾名。照後端 `library_slug` 的規則（小寫、不安全字元換成 `-`、修掉頭尾的
 * 空白、點與 `-`），但**只在名稱全是 ASCII 時給**：中日文的資料夾名在兩種檔案系統都合法，
 * 要不要用它由使用者決定，不替他決定（票 06f）。
 */
export function folderFor(name: string): string {
  if (!PRINTABLE_ASCII.test(name)) return ''
  return name
    .replace(UNSAFE_IN_NAME, '-')
    .replace(/^[ .-]+|[ .-]+$/g, '')
    .toLowerCase()
}

/** 一列落在哪裡：`<library_root>/<資料夾>`（後端 `bundled_path` 同一個拼法）。 */
export function pathUnder(libraryRoot: string, folder: string): string {
  return `${libraryRoot.replace(/\/+$/, '')}/${folder}`
}

export function problemsOf(rows: readonly LibraryDraft[]): ListProblems {
  const names = new Set<string>()
  const folders = new Set<string>()
  return {
    empty: rows.length === 0,
    rows: rows.map((row) => {
      const name = row.name.trim()
      const folder = row.folder.trim()
      const problems: RowProblems = {}
      const nameProblem = !name ? 'name_missing' : names.has(key(name)) ? 'name_taken' : null
      const folderProblem = folderProblemOf(folder, folders)
      if (nameProblem) problems.name = nameProblem
      if (folderProblem) problems.folder = folderProblem
      names.add(key(name))
      folders.add(key(folder))
      return problems
    }),
  }
}

export function hasProblems(problems: ListProblems): boolean {
  return problems.empty || problems.rows.some((row) => row.name || row.folder)
}

function folderProblemOf(folder: string, taken: ReadonlySet<string>): FolderProblem | null {
  if (!folder) return 'folder_missing'
  if (OUTSIDE_ROOT.test(folder)) return 'folder_outside_root'
  if (UNSAFE.test(folder) || [...folder].some((char) => char.charCodeAt(0) < 0x20)) {
    return 'folder_characters'
  }
  if (taken.has(key(folder))) return 'folder_taken'
  return null
}

/** 不分大小寫比重複：Windows 與 macOS 的檔案系統不分，Jellyfin 的名稱比對也不可知。 */
function key(value: string): string {
  return value.toLocaleLowerCase('en')
}

import type { RouteRefusal } from '../api/routes'

/**
 * 頁 3「建立並檢查」時「這一份選擇不成立」的那幾種（M4 票 31，實測 #50）：原本是裸的 422，畫面一律說
 * 「畫面過時了，重新整理」，而媒體庫在 Jellyfin 上沒有資料夾這種重新整理不會好。每一種說出要去哪裡改，
 * 原文收進技術細節。
 */
export const BUILD_REFUSAL = {
  library_missing: 'routes.refused.library_missing',
  library_unsupported: 'routes.refused.library_unsupported',
  target_not_in_library: 'routes.refused.target_not_in_library',
  library_without_path: 'routes.refused.library_without_path',
} as const satisfies Partial<Record<RouteRefusal, string>>

export type BuildRefusal = keyof typeof BUILD_REFUSAL

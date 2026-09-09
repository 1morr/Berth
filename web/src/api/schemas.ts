/**
 * 跨頁面共用的 API 形狀。**沒有一個是手寫的**：全部指向 `schema.d.ts`，
 * 那份由 `pnpm gen:api` 從後端的 OpenAPI 產生（plan §6）。
 *
 * 這一層只做一件事——把後端的類別名（`RouteOut`、`StepOut`）換成前端在講的名字。
 * 欄位增減、可選性、封閉集合的成員都由產出的型別決定，後端改了這裡不必跟著改，
 * 但用錯欄位的地方會在 `tsc` 就紅。
 *
 * **`./schema` 只由這個檔案 import**：產出的型別從這一個門進來，`api/*.ts` 要哪一個形狀就
 * 從這裡取 `Schemas['...']`。產生器換掉或它的輸出換形狀時，要改的地方只有一個。
 */

import type { components } from './schema'

/** 產出的 `components['schemas']`。只有 `api/*.ts` 該用它，UI 用下面命好名的那些。 */
export type Schemas = components['schemas']

/** `berth/domain/enums.py` 的 `ServiceKind`。 */
export type ServiceKind = Schemas['ServiceKind']

/** `ServiceOrigin`：逐服務的判定。 */
export type ServiceOrigin = Schemas['ServiceOrigin']

/** `StepStatus`：一條纜繩的結果。 */
export type StepStatus = Schemas['StepStatus']

/** 精靈的一步，或一個 Route 的一項檢查。 */
export type SetupStep = Schemas['StepOut']

/** `MediaKind`：一部作品是劇集還是電影（`berth/domain/enums.py`）。 */
export type MediaKind = Schemas['MediaKind']

/**
 * `TmdbProblem`：向 TMDB 要東西沒要到的四種樣子。探索頁與 Media 詳情頁共用
 * （`berth/domain/enums.py`）——兩頁問的是同一台服務，四種理由的下一步也一樣。
 */
export type TmdbProblem = NonNullable<Schemas['TmdbProblem']>

/** `Profile`：Route 的命名與解析偏好（CONTEXT.md）。 */
export type Profile = Schemas['Profile']

/** 一個 Route 或一個服務上一次檢查的結果。 */
export type HealthStatus = Schemas['HealthStatus']

export type RouteView = Schemas['RouteOut']

export type PreferenceDiff = Schemas['PreferenceDiffOut']

/** 精靈第 4 步與設定頁的漂移還原共用（brief §16.3）。 */
export type QbittorrentSetup = Schemas['QbittorrentOut']

/**
 * 三個服務的顯示順序，泊位板逐格照它畫。
 *
 * 後端把 `StepOut.step` 宣告成 `str`，所以下面這些集合在 OpenAPI 裡不存在——
 * 它們是 UI 的順序，不是 API 的形狀。`satisfies` 讓成員本身仍然受產出型別檢查。
 */
export const SERVICE_KINDS = [
  'jellyfin',
  'qbittorrent',
  'prowlarr',
] as const satisfies readonly ServiceKind[]

/** `RouteCheck`：一個 Route 的五條纜繩，順序即檢查順序。 */
export const ROUTE_CHECKS = [
  'category',
  'download_path',
  'library_path',
  'probe_visible',
  'hardlink',
] as const
export type RouteCheck = (typeof ROUTE_CHECKS)[number]

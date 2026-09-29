import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiDelete, apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { QbittorrentSetup, Schemas, ServiceKind } from './schemas'

/** `ConnectionReason`：選完之後那一次測試的理由，UI 逐服務顯示（M4 票 15）。 */
export type ConnectionReason = Schemas['ConnectionReason']

/** `ConnectionState`：測試的結果。`waiting` 是套件內那一台還在啟動，前端每 3 秒重測。 */
export type ConnectionState = Schemas['ConnectionState']

/** 一個服務的來源選擇與最後一次測試。沒選的服務不在 `SetupStatus.services` 裡。 */
export type SetupService = Schemas['ServiceOut']

export type SetupStatus = Schemas['SetupStatusOut']

/** 擁有者的 Jellyfin 帳密（頁 1，M4 票 06）。只交給 Jellyfin，Berth 不存。 */
export type OwnerInput = Schemas['OwnerIn']

export type OwnerRefusal = Refusal<Schemas['OwnerRefusal']>

const OWNER_REASONS: ReasonSet<Schemas['OwnerRefusal']> = {
  jellyfin_unresolved: true,
  invalid_credentials: true,
  not_administrator: true,
  jellyfin_failed: true,
}

/**
 * 服務頁的二選一（plan §9.3〈服務頁的共同形狀〉）。套件內只帶 `origin`（Prowlarr 讀不到掛載時
 * 另帶貼上的 key）；既有帶位址與那個服務要的憑證。
 */
export type ChoiceInput = Schemas['ChoiceIn']

export const setupStatusQueryOptions = queryOptions({
  queryKey: ['setup', 'status'],
  queryFn: () => apiGet<SetupStatus>('/setup/status'),
})

/**
 * 頁 1：成為擁有者。成功時後端發 session cookie（與 `/auth/login` 同一種），之後精靈要登入。
 * 帳密不對是 401——那是這一支的答案，不是 session 過期（`router.ts` 照樣會重跑一次守衛，無害）。
 */
/**
 * 頁 1 成為擁有者的 mutation key：帳密不對與登入同一個 401，路由不能把它當成 session 失效
 * （`router.leaveOnSignOut`，票 15 的 critique）。
 */
export const CLAIM_OWNER_KEY = ['setup', 'owner'] as const

export function claimOwner(body: OwnerInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/owner', body)
}

/** 頁 1 被拒的理由。認不得的（或根本不是拒絕，例如連不上 Berth）是 `null`。 */
export function ownerRefusalOf(error: unknown): OwnerRefusal | null {
  return parseRefusal(error, OWNER_REASONS)
}

/** 選來源、存下、測一次。擁有者成立之後改 Jellyfin 的來源是 409（擁有者是那一台上的帳號）。 */
export function chooseService(kind: ServiceKind, body: ChoiceInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>(`/setup/services/${kind}`, body)
}

/**
 * 用存下來的選擇再測一次：出問題那一頁的「重新測試」（`restart`：2 分鐘重新算），以及套件內
 * 那一台還在啟動時的輪詢（不帶）。
 */
export function retestService(kind: ServiceKind, restart = false): Promise<SetupStatus> {
  return apiPost<SetupStatus>(`/setup/services/${kind}/test`, {
    restart,
  } satisfies Schemas['RetestIn'])
}

/**
 * `JellyfinStep`：plan §9.4 的七步，順序即宣告順序、也是執行順序。前六步在頁 1（擁有者）跑，
 * 建媒體庫在頁 3（M4 票 06、15）。
 *
 * 後端把 `StepOut.step` 宣告成 `str`，所以這個集合在 OpenAPI 裡不存在——它是 UI 的
 * 顯示順序，不是 API 的形狀（`QBITTORRENT_STEPS` 同理）。
 */
export const JELLYFIN_STEPS = [
  'public_info',
  'configuration',
  'admin_user',
  'remote_access',
  'complete',
  'api_key',
  'libraries',
] as const
export type JellyfinStep = (typeof JELLYFIN_STEPS)[number]

export type JellyfinLibrary = Schemas['LibraryOut']

export type JellyfinSetup = Schemas['JellyfinSetupOut']

/** 既有 Jellyfin：以管理員帳密換 API key。 */
export type JellyfinConnectInput = Schemas['JellyfinConnectIn']

export const jellyfinSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'jellyfin'],
  queryFn: () => apiGet<JellyfinSetup>('/setup/jellyfin'),
})

export function bootstrapJellyfin(): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/bootstrap')
}

/** 套件內要建的一個媒體庫，以及它是不是已經在 Jellyfin 建好了（票 06f）。 */
export type BundledLibrary = Schemas['BundledLibraryOut']

/** 送去存的一列：內容類型 + 名稱 + 資料夾。 */
export type LibraryDraft = Schemas['BundledLibraryIn']

/**
 * 存下套件內要建的媒體庫（票 06f）。剖面改一次存一次（關掉瀏覽器回來還在），按「開始靠泊」
 * 之前也先存一次——`bootstrap` 讀的是存下來的那一份。
 */
export function saveBundledLibraries(libraries: LibraryDraft[]): Promise<JellyfinSetup> {
  return apiPut<JellyfinSetup>('/setup/jellyfin/bundled', {
    libraries,
  } satisfies Schemas['BundledLibrariesIn'])
}

export type BundledLibraryRefusal = Schemas['BundledLibraryRefusal']

/** 清單的拒絕，另帶是第幾列（0 起算）；空清單與「建好的那一列不見了」說不出是哪一列。 */
export interface BundledRefusal extends Refusal<BundledLibraryRefusal> {
  row?: number
}

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤。 */
const BUNDLED_REASONS: ReasonSet<BundledLibraryRefusal> = {
  empty: true,
  name_missing: true,
  name_taken: true,
  folder_missing: true,
  folder_taken: true,
  folder_outside_root: true,
  folder_characters: true,
  built_changed: true,
}

/** 清單被後端擋下來的理由。剖面先用同一組規則擋過，所以到得了這裡的多半是另一個分頁改過了。 */
export function bundledRefusalOf(error: unknown): BundledRefusal | null {
  const refusal = parseRefusal(error, BUNDLED_REASONS)
  // 第二個條件在 `parseRefusal` 回了東西之後永遠成立，寫出來是為了 TypeScript 的縮窄
  // （`routeRefusalOf` 同一個寫法）。
  if (refusal === null || !(error instanceof ApiError)) return refusal
  const { row } = error.detail as Partial<Schemas['BundledLibraryRefusalOut']>
  return typeof row === 'number' ? { ...refusal, row } : refusal
}

export function connectJellyfin(body: JellyfinConnectInput): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/connect', body)
}

export function addLibraryPath(library: string): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/libraries/paths', {
    library,
  } satisfies Schemas['LibraryPathIn'])
}

/** --- 頁 2：qBittorrent（plan §9.3、§8.1）--- */

/** `QbittorrentStep`：一個鍵一條纜繩，值就是 `app/setPreferences` 的鍵名。 */
export const QBITTORRENT_STEPS = [
  'temp_path_enabled',
  'temp_path',
  'save_path',
  'auto_tmm_enabled',
  'category_changed_tmm_enabled',
  'web_ui_password',
] as const
export type QbittorrentStep = (typeof QBITTORRENT_STEPS)[number]

export const qbittorrentSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'qbittorrent'],
  queryFn: () => apiGet<QbittorrentSetup>('/setup/qbittorrent/diff'),
})

/**
 * 套件內 qBittorrent / Prowlarr 自己的介面登入（M4 票 07）。`reuse_owner` 是「沿用 Jellyfin 帳密」
 * （M4 票 15）：帳號由後端填成擁有者，密碼先向 Jellyfin 驗過。
 */
export type InterfaceLogin = Schemas['InterfaceLoginIn']

export type InterfaceLoginRefusal = Refusal<Schemas['InterfaceLoginRefusal']>

const LOGIN_REASONS: ReasonSet<Schemas['InterfaceLoginRefusal']> = {
  owner_password: true,
  jellyfin_unreachable: true,
}

/** 沿用 Jellyfin 帳密時 Jellyfin 那一關沒過的理由；其餘的失敗是 `null`。 */
export function loginRefusalOf(error: unknown): InterfaceLoginRefusal | null {
  return parseRefusal(error, LOGIN_REASONS)
}

/** `login` 是泊位上填的 WebUI 登入；`null` 是登入照舊。 */
export function applyQbittorrent(login: InterfaceLogin | null): Promise<QbittorrentSetup> {
  return apiPost<QbittorrentSetup>('/setup/qbittorrent/apply', {
    login,
  } satisfies Schemas['QbittorrentApplyIn'])
}

/** 設定頁的「更新登入」：只換套件內那一台的 WebUI 登入，五個鍵不動。 */
export function setQbittorrentLogin(login: InterfaceLogin): Promise<QbittorrentSetup> {
  return apiPut<QbittorrentSetup>('/setup/qbittorrent/login', login)
}

/** --- 頁 4、5：Prowlarr 與索引站、TMDB（plan §9.3、§8.3、§8.4）--- */

/** `IndexerKind`：既有路徑的兩種接法。 */
export type IndexerKind = Schemas['IndexerKind']

/** Prowlarr 裡已經有的一站（M4 票 09 的「已加入」）。 */
export type IndexerSite = Schemas['IndexerSiteOut']

/** 還沒加入、Berth 加得了的一站（M4 票 09 的「加站」）：推薦清單與其他公開的 torrent 站。 */
export type IndexerCandidate = Schemas['IndexerCandidateOut']

/** 一站通不通：「測試」的回答，也是上一次「加入」對那一站的結論。 */
export type SiteCheck = Schemas['SiteCheckOut']

export type SiteFailure = NonNullable<SiteCheck['reason']>

export type IndexerSetup = Schemas['IndexerSetupOut']

/** 既有 Prowlarr 或任意 Torznab 的連線表單。 */
export type IndexerConnectInput = Schemas['IndexerConnectIn']

export type TmdbSetup = Schemas['TmdbSetupOut']

/** 試搜的整份結果：逐站一列（票 06e）。 */
export type TrialSearchResult = Schemas['IndexerSearchOut']

export type SiteSearch = Schemas['SiteSearchOut']

export const indexerSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'indexers'],
  queryFn: () => apiGet<IndexerSetup>('/setup/indexers'),
})

export const tmdbSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'tmdb'],
  queryFn: () => apiGet<TmdbSetup>('/setup/tmdb'),
})

/** `login` 是泊位上填的 Prowlarr 介面登入；`null` 是登入照舊（設定頁加站）。 */
export function applyIndexers({
  indexers,
  login,
}: {
  indexers: string[]
  login: InterfaceLogin | null
}): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/apply', {
    indexers,
    login,
  } satisfies Schemas['IndexerApplyIn'])
}

/** 設定頁的「更新登入」：只換套件內 Prowlarr 的介面登入，等它重啟回來。 */
export function setIndexerLogin(login: InterfaceLogin): Promise<IndexerSetup> {
  return apiPut<IndexerSetup>('/setup/indexers/login', login)
}

export function connectIndexer(body: IndexerConnectInput): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/connect', body)
}

export function skipIndexers(skipped: boolean): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/skip', { skipped } satisfies Schemas['SkipIn'])
}

/**
 * 「測試」（M4 票 09）：逐站問套件內的 Prowlarr 通不通，什麼都不建立。只讀，但要 Prowlarr 現場
 * 去連那些站，所以是按了才問。
 */
export async function testIndexers(indexers: string[]): Promise<SiteCheck[]> {
  const body = await apiPost<Schemas['IndexerTestOut']>('/setup/indexers/test', {
    indexers,
  } satisfies Schemas['IndexerTestIn'])
  return body.checks
}

/**
 * 加入之後的試搜（票 06e）。只讀，但要 Prowlarr 現場去連每一個站，所以是按了才問，
 * 不是開頁就問。空白的查詢回各站最新的發佈。`indexerId` 是那一列的「搜尋」，只問那一站。
 */
export function searchIndexers(
  query: string,
  indexerId: number | null = null,
): Promise<TrialSearchResult> {
  const params = new URLSearchParams({ query })
  if (indexerId !== null) params.set('indexer_id', String(indexerId))
  return apiGet<TrialSearchResult>(`/setup/indexers/search?${params}`)
}

/** 從套件內的 Prowlarr 移除一站（票 06e）。回的是整份索引站狀態：那一站與它的加入結果都不在了。 */
export function removeIndexer(id: number): Promise<IndexerSetup> {
  return apiDelete<IndexerSetup>(`/setup/indexers/${id}`)
}

/** TMDB 頁沒有 `skip`：憑證是使用者自備的必填項，測得過才走得到完成（票 02b）。 */
export function testTmdb(api_key: string): Promise<TmdbSetup> {
  return apiPost<TmdbSetup>('/setup/tmdb/test', { api_key } satisfies Schemas['TmdbTestIn'])
}

/** --- 頁 3：媒體庫與路徑（plan §9.3、§9.5）--- */

export type LibraryChoice = Schemas['LibraryChoiceOut']

export type RouteSetup = Schemas['RouteSetupOut']

export type RouteSelectionInput = Schemas['RouteSelectionIn']

export const routeSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'routes'],
  queryFn: () => apiGet<RouteSetup>('/setup/routes'),
})

export function buildRoutes(selections: RouteSelectionInput[]): Promise<RouteSetup> {
  return apiPost<RouteSetup>('/setup/routes', { selections } satisfies Schemas['RoutesIn'])
}

/**
 * 頁 3 每條 Route 底下的刪除（票 14a）。與設定頁的 `deleteRoute` 同一個命令、同一種拒絕，
 * 只是跟著精靈的門禁：精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有 admin。
 */
export function deleteSetupRoute(id: number): Promise<void> {
  return apiDelete(`/setup/routes/${id}`)
}

/** 寫下 `settings.setup.completed`。**之後 `setup/*` 就要登入了**（票 07）。 */
export function completeSetup(): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/complete')
}

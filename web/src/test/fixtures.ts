import type {
  IndexerOption,
  IndexerSetup,
  JellyfinLibrary,
  JellyfinSetup,
  LibraryChoice,
  RouteSetup,
  ServiceDetection,
  SetupStatus,
  TmdbSetup,
} from '../api/setup'
import type {
  PollerView,
  PreferenceDiff,
  QbittorrentSetup,
  RouteView,
  SetupStep,
} from '../api/schemas'
import type { LibraryOption, ManagedRoute } from '../api/routes'
import type { Discover, DiscoverItem } from '../api/discover'
import type { HealthDetail, ServiceHealth } from '../api/health'
import type { StubRoute } from './fetch'

/** 檢查與精靈都用這一個時間點，畫面上的「上次檢查」才是同一輪。 */
const CHECKED_AT = '2026-09-08T12:00:00Z'

/** 精靈狀態的測試建構子。預設是乾淨安裝的第 1 步。 */
export function setupStatus(overrides: Partial<SetupStatus> = {}): SetupStatus {
  return {
    completed: false,
    current_step: 1,
    admin_created: false,
    admin_username: '',
    interface_username: '',
    jellyfin_owns_account: false,
    apply_to_services: true,
    services: [],
    waited_seconds: 0,
    window_seconds: 120,
    ...overrides,
  }
}

export function detection(overrides: Partial<ServiceDetection> = {}): ServiceDetection {
  return {
    kind: 'jellyfin',
    origin: 'bundled',
    reason: 'setup_pending',
    detail: '12.1.0',
    base_url: 'http://jellyfin:8096',
    // 探測 compose 主機名的結果，不是使用者填的連線表單。
    configured: false,
    resolved: true,
    ...overrides,
  }
}

/** 乾淨 compose：三個服務都判為套件內。 */
export const ALL_BUNDLED: ServiceDetection[] = [
  detection(),
  detection({
    kind: 'qbittorrent',
    reason: 'anonymous_ok',
    detail: 'v5.2.3 · Web API 2.15.1',
    base_url: 'http://qbittorrent:8080',
  }),
  detection({
    kind: 'prowlarr',
    reason: 'no_indexers',
    detail: '',
    base_url: 'http://prowlarr:9696',
  }),
]

/** 第 3 步狀態的測試建構子。預設是「套件內、還沒跑過」。 */
export function jellyfinSetup(overrides: Partial<JellyfinSetup> = {}): JellyfinSetup {
  return {
    origin: 'bundled',
    base_url: 'http://jellyfin:8096',
    api_key_present: false,
    steps: [],
    libraries: [],
    version: '',
    version_supported: true,
    ...overrides,
  }
}

export function step(key: string, status: SetupStep['status'], detail = '', error = ''): SetupStep {
  return { step: key, status, detail, error }
}

/** 七步全過的一輪。 */
export const SEQUENCE_DONE: SetupStep[] = [
  step('public_info', 'ok', '12.1.0'),
  step('configuration', 'ok', 'zh-TW · TW'),
  step('admin_user', 'ok', 'skipper'),
  step('libraries', 'ok', 'Movies · TV · Anime'),
  step('remote_access', 'ok'),
  step('complete', 'ok'),
  step('api_key', 'ok', 'Berth'),
]

export function library(overrides: Partial<JellyfinLibrary> = {}): JellyfinLibrary {
  return {
    name: 'Films',
    collection_type: 'movies',
    locations: ['/volume1/media/films'],
    metadata_fetchers: ['TheMovieDb'],
    uses_tvdb: false,
    berth_path: '/data/library/films',
    has_berth_path: false,
    ...overrides,
  }
}

/** 第 4 步狀態的測試建構子。預設是「套件內、乾淨實例、五個鍵全不同」。 */
export function qbittorrentSetup(overrides: Partial<QbittorrentSetup> = {}): QbittorrentSetup {
  return {
    origin: 'bundled',
    base_url: 'http://qbittorrent:8080',
    version: 'v5.2.3',
    webapi_version: '2.15.1',
    supported: true,
    blocked: false,
    reachable: true,
    // 錄製回應裡的乾淨實例值（brief §20.7）。
    diffs: [
      diff('temp_path_enabled', 'false', 'true'),
      diff('temp_path', '/downloads/incomplete', '/data/torrent/incomplete'),
      diff('save_path', '/downloads', '/data/torrent/complete'),
      diff('auto_tmm_enabled', 'false', 'true'),
      diff('category_changed_tmm_enabled', 'false', 'true'),
    ],
    steps: [],
    temp_path_warning: false,
    sets_password: true,
    error: '',
    ...overrides,
  }
}

export function diff(key: string, current: string, recommended: string): PreferenceDiff {
  return { key, current, recommended, differs: current !== recommended }
}

/** 十個預設站，名稱與 privacy 取自真的 `indexer/schema`（`tests/fixtures/`）。 */
export const DEFAULT_OPTIONS: IndexerOption[] = [
  option('nyaasi', 'Nyaa.si'),
  option('dmhy', 'dmhy'),
  option('Anidex', 'Anidex'),
  option('animetosho-xyz', 'Anime Tosho', 'semiPrivate'),
  option('acgrip', 'ACG.RIP'),
  option('mikan', 'Mikan'),
  option('1337x', '1337x'),
  option('yts', 'YTS'),
  option('eztv', 'EZTV'),
  option('thepiratebay', 'The Pirate Bay'),
]

export function option(
  definition_name: string,
  name: string,
  privacy = 'public',
  present = false,
): IndexerOption {
  return { definition_name, name, privacy, present }
}

/** 第 5 步狀態的測試建構子。預設是「套件內 Prowlarr、十個站都還沒加」。 */
export function indexerSetup(overrides: Partial<IndexerSetup> = {}): IndexerSetup {
  return {
    origin: 'bundled',
    kind: 'prowlarr',
    base_url: 'http://prowlarr:9696',
    api_key_present: true,
    reachable: true,
    options: DEFAULT_OPTIONS,
    steps: [],
    skipped: false,
    sets_password: true,
    error: '',
    ...overrides,
  }
}

/** 第 6 步狀態的測試建構子。預設是「還沒填 key、還沒測過」。 */
export function tmdbSetup(overrides: Partial<TmdbSetup> = {}): TmdbSetup {
  return { api_key_present: false, verified: false, steps: [], ...overrides }
}

/** 第 7 步狀態的測試建構子。預設是「套件內、三個媒體庫、還沒建 Route」。 */
export function routeSetup(overrides: Partial<RouteSetup> = {}): RouteSetup {
  return {
    origin: 'bundled',
    library_root: '/data/library',
    complete_root: '/data/torrent/complete',
    libraries: [
      libraryChoice({ name: 'Movies', collection_type: 'movies' }),
      libraryChoice({ name: 'TV' }),
      libraryChoice({ name: 'Anime' }),
    ],
    routes: [],
    ready: false,
    completed: false,
    ...overrides,
  }
}

export function libraryChoice(overrides: Partial<LibraryChoice> = {}): LibraryChoice {
  const name = overrides.name ?? 'TV'
  const slug = name.toLowerCase()
  return {
    name,
    collection_type: 'tvshows',
    locations: [`/data/library/${slug}`],
    berth_path: `/data/library/${slug}`,
    has_berth_path: true,
    uses_tvdb: false,
    supported: true,
    has_route: false,
    target_path: `/data/library/${slug}`,
    ...overrides,
  }
}

export function routeView(overrides: Partial<RouteView> = {}): RouteView {
  const library = overrides.library ?? 'TV'
  const slug = overrides.slug ?? library.toLowerCase()
  return {
    id: 2,
    slug,
    name: library,
    library,
    collection_type: 'tvshows',
    target_path: `/data/library/${slug}`,
    category: `berth-${slug}`,
    save_path: `/data/torrent/complete/${slug}`,
    enabled: true,
    health: 'ok',
    checks: CHECKS_PASSED,
    cross_device: false,
    checked_at: CHECKED_AT,
    last_ok_at: CHECKED_AT,
    ...overrides,
  }
}

/** --- Route 設定頁（票 14）--- */

/** 設定頁上的一列：Route 本身與有多少東西指著它。預設沒有人用，刪得掉。 */
export function managedRoute(overrides: Partial<ManagedRoute> = {}): ManagedRoute {
  return { route: routeView(), jobs: 0, ledger_entries: 0, in_use: false, ...overrides }
}

/** Jellyfin 現查回來的一個媒體庫。預設是掛了兩顆碟、第一顆已經是 TV 的那一個。 */
export function libraryOption(overrides: Partial<LibraryOption> = {}): LibraryOption {
  return {
    item_id: 'item-1',
    name: 'TV',
    collection_type: 'tvshows',
    paths: [
      { path: '/data/library/tv', route_name: 'TV' },
      { path: '/mnt/disk2/tv', route_name: null },
    ],
    supported: true,
    uses_tvdb: false,
    ...overrides,
  }
}

/** 五條纜繩全繫上的一輪，`detail` 是實測值的形狀（inode、可用空間）。 */
export const CHECKS_PASSED: SetupStep[] = [
  step('category', 'ok', 'berth-tv → /data/torrent/complete/tv'),
  step('download_path', 'ok', '/data/torrent/complete · /data/torrent/complete/tv'),
  step('library_path', 'ok', '/data/library/tv'),
  step('probe_visible', 'ok', '/data/library/tv'),
  step('hardlink', 'ok', 'dev=70 · inode=8162774324533690 · 137.4 GB free'),
]

/** --- 健康檢查（票 10）--- */

export function serviceHealth(overrides: Partial<ServiceHealth> = {}): ServiceHealth {
  return {
    kind: 'jellyfin',
    origin: 'bundled',
    base_url: 'http://jellyfin:8096',
    status: 'ok',
    detail: '12.1.0 · 3 libraries',
    error: '',
    checked_at: CHECKED_AT,
    last_ok_at: CHECKED_AT,
    failures: 0,
    configured: true,
    drift: [],
    banned: false,
    unsupported: false,
    ...overrides,
  }
}

/** 四項全綠的一輪。單一項要變紅時覆寫 `services` 裡的那一列。 */
export function healthDetail(overrides: Partial<HealthDetail> = {}): HealthDetail {
  return {
    status: 'ok',
    checked_at: CHECKED_AT,
    interval_seconds: 300,
    services: [
      serviceHealth(),
      serviceHealth({
        kind: 'qbittorrent',
        base_url: 'http://qbittorrent:8080',
        detail: 'v5.2.3 · Web API 2.15.1',
      }),
      serviceHealth({
        kind: 'prowlarr',
        base_url: 'http://prowlarr:9696',
        detail: '10',
      }),
    ],
    routes_status: 'ok',
    routes: [routeView()],
    poller: pollerView(),
    ...overrides,
  }
}

/** 上一輪成功、沒有無主 torrent 的下載迴圈（票 10）。失敗那一種由呼叫端覆寫。 */
export function pollerView(overrides: Partial<PollerView> = {}): PollerView {
  return {
    checked_at: CHECKED_AT,
    failures: 0,
    error: '',
    interval_seconds: 5,
    unknown_torrents: [],
    ...overrides,
  }
}

/** 一項紅了的那一輪：其餘三項不受影響（票 10 驗收）。 */
export function withFailedService(
  kind: ServiceHealth['kind'],
  error: string,
  overrides: Partial<ServiceHealth> = {},
): HealthDetail {
  const base = healthDetail()
  return {
    ...base,
    status: 'degraded',
    services: base.services.map((row) =>
      row.kind === kind
        ? { ...row, status: 'failed', error, failures: 1, last_ok_at: CHECKED_AT, ...overrides }
        : row,
    ),
  }
}

/** 探索頁一個 feed 的回應。路過這一頁的測試給空牆就夠了。 */
export function discoverWall(items: DiscoverItem[] = []): StubRoute {
  return { body: { items, problem: null, detail: '' } satisfies Discover }
}

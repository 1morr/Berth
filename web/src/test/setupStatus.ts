import type {
  IndexerOption,
  IndexerSetup,
  JellyfinLibrary,
  JellyfinSetup,
  PreferenceDiff,
  QbittorrentSetup,
  ServiceDetection,
  SetupStatus,
  SetupStep,
  TmdbSetup,
} from '../api/setup'

/** 精靈狀態的測試建構子。預設是乾淨安裝的第 1 步。 */
export function setupStatus(overrides: Partial<SetupStatus> = {}): SetupStatus {
  return {
    completed: false,
    current_step: 1,
    admin_created: false,
    admin_username: '',
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
    detail: '10.11.11',
    base_url: 'http://jellyfin:8096',
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
    merge_versions_installed: false,
    merge_movies_task_id: '',
    merge_episodes_task_id: '',
    ...overrides,
  }
}

export function step(key: string, status: SetupStep['status'], detail = '', error = ''): SetupStep {
  return { step: key, status, detail, error }
}

/** 九步全過的一輪。 */
export const SEQUENCE_DONE: SetupStep[] = [
  step('public_info', 'ok', '10.11.11'),
  step('configuration', 'ok', 'zh-TW · TW'),
  step('admin_user', 'ok', 'skipper'),
  step('libraries', 'ok', 'Movies · TV · Anime'),
  step('remote_access', 'ok'),
  step('complete', 'ok'),
  step('api_key', 'ok', 'Berth'),
  step('plugin', 'ok', '10.11.0.1'),
  step('tasks', 'ok', 'fd957c84 · dcaf151d'),
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

/** 第 6 步狀態的測試建構子。預設是「用內建憑證、還沒測過」。 */
export function tmdbSetup(overrides: Partial<TmdbSetup> = {}): TmdbSetup {
  return { using_project_credential: true, steps: [], skipped: false, ...overrides }
}

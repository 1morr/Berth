import type {
  JellyfinLibrary,
  JellyfinSetup,
  ServiceDetection,
  SetupStatus,
  SetupStep,
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

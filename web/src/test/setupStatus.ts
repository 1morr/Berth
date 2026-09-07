import type { ServiceDetection, SetupStatus } from '../api/setup'

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

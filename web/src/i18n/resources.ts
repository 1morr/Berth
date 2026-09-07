// UI 文案的唯一來源。檔名 token、log 與識別符保持英文（brief §16.2）。
// zh-Hant 與 en 並列，兩邊必須同時維護——en 是一等公民，不是之後補的譯本（PRODUCT.md）。

/** 同一份鍵樹，值放寬成 string——少一個 key、多一個 key 或層級不同都是編譯錯誤。 */
type Translations<T> = {
  [K in keyof T]: T[K] extends string ? string : Translations<T[K]>
}

const zhHant = {
  app: {
    name: 'Berth',
    tagline: '媒體取得與入庫協調器',
  },
  language: {
    label: '語言',
    zh: 'ZH',
    en: 'EN',
  },
  board: {
    title: '泊位板',
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    source: '來源',
    library: '媒體庫路徑',
    unassigned: '未指派',
  },
  setup: {
    title: '設定精靈',
    stage: '前置',
    step: '第 {{current}} 步，共 {{total}} 步',
    resumed: '進度已保留，關掉瀏覽器再回來會回到這一步。',
  },
  admin: {
    title: '建立 Berth 管理員',
    lede: '這組帳密是 Berth 的管理員。之後的步驟會用它建立 Jellyfin 管理員。',
    cutaway: {
      title: '將會寫入',
      berth: 'Berth 管理員',
      jellyfin: 'Jellyfin 管理員（第 3 步）',
      qbittorrent: 'qBittorrent WebUI 密碼（第 4 步）',
      prowlarr: 'Prowlarr 介面登入（第 5 步）',
      skipped: '不套用',
    },
    field: {
      username: '帳號',
      password: '密碼',
      apply: '同一組帳密也套用到 qBittorrent 與 Prowlarr 介面',
      applyHint: '只影響套件內的服務。你自己的既有服務不會被改動。',
    },
    submit: '建立管理員',
    submitting: '建立中…',
    chip: '已建立',
    saved: '管理員已建立：{{username}}',
    change: '改帳密',
    error: {
      blank: '帳號與密碼都要填。',
      failed: '存不進去。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
    },
  },
  detect: {
    title: '偵測服務',
    lede: 'Berth 逐一探測三個 compose 主機名，判斷每個服務是套件內的還是你自己的。',
    cutaway: {
      title: '將會探測',
      verdict: '判定依據',
      jellyfin: '初始精靈是否跑過',
      qbittorrent: '免密是否進得去',
      prowlarr: '讀不讀得到 API key、有沒有索引站',
    },
    run: '開始探測',
    rerun: '重新探測',
    running: '探測中…',
    retry: '重試',
    waitingLabel: '等待中',
    waiting: '{{waited}} / {{window}} 秒',
    waitingHint: '容器還在啟動。Berth 會持續探測到上限為止。',
    failed: '探測沒跑完。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
    empty: '還沒探測過。',
  },
  service: {
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    prowlarr: 'Prowlarr',
  },
  origin: {
    bundled: '套件內',
    existing: '既有',
    pending: '探測中',
    timeout: '逾時',
  },
  reason: {
    setup_pending: '初始精靈尚未跑過，Berth 可以全自動接手',
    setup_completed: '已經跑過自己的初始精靈',
    anonymous_ok: '免密進得去 Web API',
    auth_required: '要求帳密',
    no_indexers: '讀得到 API key 且一個索引站都沒有',
    has_indexers: '已經設定過索引站',
    api_key_missing: '唯讀掛載與環境變數都讀不到 API key',
    not_deployed: '主機名解不到，不在這套 compose 裡',
    unreachable: '主機名解得到但連不上',
    protocol_mismatch: '連得上，但回的東西不是這個服務',
    connected: '連線測試通過',
  },
  detail: {
    version: '版本',
    indexers: '索引站',
  },
  connect: {
    title: '連到你的 {{service}}',
    field: {
      baseUrl: '位址',
      apiKey: 'API key',
      username: '帳號',
      password: '密碼',
    },
    hint: {
      jellyfin: '管理員登入與 API key 在第 3 步；這裡只確認位址連得到。',
      qbittorrent: '免密的話帳密留空。',
      prowlarr: '在 Prowlarr 的「設定 → 一般 → 安全性」找得到 API key。',
    },
    submit: '測試連線',
    submitting: '測試中…',
    fix: {
      title: '手動步驟',
      notDeployed: '把 {{service}} 加回 .env 的 COMPOSE_PROFILES，或在上面填你自己那一台的位址。',
      unreachable: '在宿主上確認容器活著，再確認 port 沒有被改掉：',
    },
  },
  health: {
    title: '健康',
    checking: '檢查中…',
    unreachable: '連不上 Berth 後端。確認程序是否還在執行。',
    backend: '後端',
    version: '版本',
    value: {
      ok: '正常',
      degraded: '降級',
    },
  },
  common: {
    failed: '失敗',
    show: '顯示',
    hide: '隱藏',
    copy: '複製',
    copied: '已複製',
  },
} as const

const en: Translations<typeof zhHant> = {
  app: {
    name: 'Berth',
    tagline: 'Media acquisition and import coordinator',
  },
  language: {
    label: 'Language',
    zh: 'ZH',
    en: 'EN',
  },
  board: {
    title: 'Berth board',
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    source: 'Source',
    library: 'Library paths',
    unassigned: 'Unassigned',
  },
  setup: {
    title: 'Setup wizard',
    stage: 'Pre-berth',
    step: 'Step {{current}} of {{total}}',
    resumed: 'Progress is saved. Close the browser and you come back to this step.',
  },
  admin: {
    title: 'Create the Berth administrator',
    lede: 'This account administers Berth. Later steps use it to create the Jellyfin administrator.',
    cutaway: {
      title: 'Will be written',
      berth: 'Berth administrator',
      jellyfin: 'Jellyfin administrator (step 3)',
      qbittorrent: 'qBittorrent WebUI password (step 4)',
      prowlarr: 'Prowlarr interface login (step 5)',
      skipped: 'Not applied',
    },
    field: {
      username: 'Username',
      password: 'Password',
      apply: 'Use the same credentials for the qBittorrent and Prowlarr interfaces',
      applyHint: 'Bundled services only. Your own existing services are never changed.',
    },
    submit: 'Create administrator',
    submitting: 'Creating…',
    chip: 'Created',
    saved: 'Administrator created: {{username}}',
    change: 'Change credentials',
    error: {
      blank: 'Username and password are both required.',
      failed:
        'Could not save. The Berth backend may not be running — check the container and retry.',
    },
  },
  detect: {
    title: 'Detect services',
    lede: 'Berth probes the three compose hostnames and decides whether each service is bundled or your own.',
    cutaway: {
      title: 'Will be probed',
      verdict: 'Decided on',
      jellyfin: 'Whether the startup wizard has run',
      qbittorrent: 'Whether the API answers without credentials',
      prowlarr: 'Whether the API key is readable and any indexer exists',
    },
    run: 'Start probing',
    rerun: 'Probe again',
    running: 'Probing…',
    retry: 'Retry',
    waitingLabel: 'Waiting',
    waiting: '{{waited}} of {{window}} seconds',
    waitingHint: 'Containers are still starting. Berth keeps probing until the limit.',
    failed: 'The probe did not finish. The Berth backend may not be running — check it and retry.',
    empty: 'Not probed yet.',
  },
  service: {
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    prowlarr: 'Prowlarr',
  },
  origin: {
    bundled: 'Bundled',
    existing: 'Existing',
    pending: 'Probing',
    timeout: 'Timed out',
  },
  reason: {
    setup_pending: 'Startup wizard has not run; Berth can take it over',
    setup_completed: 'Already ran its own startup wizard',
    anonymous_ok: 'Web API answers without credentials',
    auth_required: 'Asks for credentials',
    no_indexers: 'API key readable and no indexer configured',
    has_indexers: 'Indexers are already configured',
    api_key_missing: 'No API key in the read-only mount or the environment',
    not_deployed: 'Hostname does not resolve; not part of this compose project',
    unreachable: 'Hostname resolves but nothing answers',
    protocol_mismatch: 'Something answered, but it is not this service',
    connected: 'Connection test passed',
  },
  detail: {
    version: 'Version',
    indexers: 'Indexers',
  },
  connect: {
    title: 'Connect to your {{service}}',
    field: {
      baseUrl: 'Address',
      apiKey: 'API key',
      username: 'Username',
      password: 'Password',
    },
    hint: {
      jellyfin: 'Admin login and API key come in step 3; this only confirms the address answers.',
      qbittorrent: 'Leave the credentials empty if the WebUI has no password.',
      prowlarr: 'The API key is under Settings → General → Security in Prowlarr.',
    },
    submit: 'Test connection',
    submitting: 'Testing…',
    fix: {
      title: 'Manual steps',
      notDeployed:
        'Put {{service}} back into COMPOSE_PROFILES in .env, or enter the address of your own instance above.',
      unreachable:
        'Check the container is running on the host, then check the port was not changed:',
    },
  },
  health: {
    title: 'Health',
    checking: 'Checking…',
    unreachable: 'Cannot reach the Berth backend. Check that the process is still running.',
    backend: 'Backend',
    version: 'Version',
    value: {
      ok: 'OK',
      degraded: 'Degraded',
    },
  },
  common: {
    failed: 'Failed',
    show: 'Show',
    hide: 'Hide',
    copy: 'Copy',
    copied: 'Copied',
  },
}

export const resources = {
  'zh-Hant': { translation: zhHant },
  en: { translation: en },
} as const

export const SUPPORTED_LANGUAGES = ['zh-Hant', 'en'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

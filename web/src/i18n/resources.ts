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
    stage: {
      pre: '前置',
      berth: '泊位 {{code}}',
    },
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
    continue: '前往泊位 1',
    waitingLabel: '等待中',
    waiting: '{{waited}} / {{window}} 秒',
    waitingHint: '容器還在啟動。Berth 會持續探測到上限為止。',
    failed: '探測沒跑完。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
    empty: '還沒探測過。',
    done: '{{count}} 個服務已判定',
  },
  service: {
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    prowlarr: 'Prowlarr',
  },
  status: {
    ok: '已完成',
    skipped: '已經是這樣',
    failed: '失敗',
    running: '進行中',
    pending: '尚未執行',
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
  jellyfin: {
    unreachable: '讀不到 Jellyfin 這一步的狀態。確認 Berth 後端還在跑。',
    cutaway: {
      sequence: '將會做什麼',
      server: '這台 Jellyfin',
      apiKey: 'API key',
      held: '已取得',
      absent: '尚未取得',
      libraries: '媒體庫',
      mergeVersions: 'MergeVersions',
      installed: '已安裝',
      notInstalled: '未安裝',
    },
    step: {
      public_info: '確認初始精靈還沒跑過',
      configuration: '語言與 metadata 地區',
      admin_user: '以 Berth 的帳密建立管理員',
      libraries: '建立 Movies / TV / Anime 三個媒體庫',
      remote_access: '開啟遠端存取',
      complete: '結束初始精靈',
      api_key: '建立 Berth 專用的 API key',
      plugin: '安裝 MergeVersions 並重啟',
      tasks: '記下兩個合併任務的 Id',
    },
    bundled: {
      title: '接手這台 Jellyfin',
      lede: '這台 Jellyfin 還沒跑過自己的初始精靈，所以 Berth 可以全部代辦。每一步都可以重按：已經對的那幾步會標成「已經是這樣」，不會做第二次。',
      run: '開始靠泊',
      rerun: '重新跑一次',
      retry: '重試失敗的那一步',
      running: '進行中…',
      done: '這個泊位的事做完了。Jellyfin 有 Berth 管理員、三個媒體庫與 MergeVersions。',
      requestFailed: '請求沒跑完。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
    },
    existing: {
      title: '接入你的 Jellyfin',
      lede: '這台 Jellyfin 已經跑過自己的初始精靈，所以 Berth 只做檢查。它不會建立媒體庫、不會改你既有媒體庫的設定，也不會刪任何東西。',
      username: 'Jellyfin 管理員帳號',
      password: 'Jellyfin 管理員密碼',
      passwordHint: '只用來換一把 Berth 專用的 API key，不會存下來。',
      signIn: '登入並建立 API key',
      signInAgain: '重新登入',
      signingIn: '登入中…',
      requestFailed: '請求沒跑完。確認位址與 Berth 後端的狀態後再試一次。',
    },
    libraries: {
      title: '媒體庫與路徑',
      lede: '全部是 Jellyfin 自己報出來的。舊路徑一律原地不動——Berth 只會多加一條自己寫入用的路徑。',
      empty:
        '這台 Jellyfin 一個媒體庫都沒有。先在 Jellyfin 建一個媒體庫再回來，Berth 才有地方寫入。',
      emptyLabel: '沒有媒體庫',
      wired: '已接上',
      unwired: '待指派',
      paths: '路徑',
      berthPath: 'Berth 寫入',
      fetchers: 'metadata 來源',
      warningLabel: '警告',
      tvdb: '這個媒體庫用 TVDB 取 metadata。Berth 第一階段以 TMDB 對應作品，季集編號可能與這裡不一致。不阻擋，但比對出錯時先看這裡。',
      willAdd: '將會加入這一條路徑',
      addPath: '加入 Berth 路徑',
      addConfirm: '確認加入',
      adding: '加入中…',
      addWarning:
        '會對媒體庫「{{library}}」加上 {{path}}。舊路徑不動、不會重新掃描、觀看紀錄不受影響。',
      addFailed:
        '路徑沒加上去。最常見的原因是 Berth 與 Jellyfin 沒把同一個宿主目錄掛在同一個容器路徑——Berth 建得出目錄，Jellyfin 卻看不到。也可以在 Jellyfin 自己的媒體庫設定裡手動加這一條：',
    },
    plugin: {
      title: 'MergeVersions 插件',
      lede: '同一集有多個版本時，Jellyfin 預設會顯示成兩個重複的條目。這個插件把它們合併成一個條目的多個版本。',
      install: '安裝 MergeVersions',
      confirm: '確認安裝並重啟',
      installing: '安裝中…',
      warning:
        '會在你的 Jellyfin 加入 danieladov 插件庫、安裝 MergeVersions，然後重啟 Jellyfin。重啟期間正在播放的人會斷線，通常一分鐘內回來。',
      already: '版本 {{version}}；合併任務 Id {{movies}} 與 {{episodes}} 已記下。',
    },
    fix: {
      generic: '在你的 Jellyfin 上手動做這一步，然後回來重試。',
      public_info: '確認 Jellyfin 容器活著，再確認位址與 port 沒有被改掉：',
      configuration: '在 Jellyfin 自己的初始精靈把語言設成繁體中文、地區設成台灣：',
      admin_user: '在 Jellyfin 自己的初始精靈建立管理員，帳密要與這裡的第 1 步一致：',
      libraries:
        '在 Jellyfin 的「媒體庫」手動建立 Movies、TV、Anime 三個媒體庫，關掉即時監控、Specials 顯示名稱填 Specials：',
      remote_access: '在 Jellyfin 的初始精靈開啟遠端存取：',
      complete: '在 Jellyfin 自己的初始精靈按到最後一頁完成它：',
      api_key: '在 Jellyfin 的「API 金鑰」建立一把名為 Berth 的金鑰：',
      plugin:
        '在 Jellyfin 的「插件 → 儲存庫」加入下面這個 manifest，安裝 Merge Versions，然後重啟 Jellyfin：',
      tasks:
        '確認 MergeVersions 已啟用，並在「排程任務」看得到 Merge All Movies 與 Merge All Episodes：',
      retryHint: '手動做完之後按下面的按鈕，Berth 只會重跑還沒完成的步驟。',
    },
  },
  qbittorrent: {
    title: '套用建議的 qBittorrent 設定',
    unreachable: '讀不到 qBittorrent 這一步的狀態。確認 Berth 後端還在跑。',
    lede: {
      bundled:
        '這台 qBittorrent 是套件內的，Berth 直接改它的偏好。下面五個鍵是 Berth 送單與入庫要用的，只有與現值不同的才會被寫。',
      existing:
        '這台 qBittorrent 是你自己的。Berth 只寫下面這幾個鍵，不動其他任何設定，也不碰你既有的 torrent。',
    },
    cutaway: {
      server: '這台 qBittorrent',
      webapi: 'Web API',
      password: 'WebUI 密碼',
      willSet: '將設為第 1 步的帳密',
      diff: '將會寫入的鍵',
      key: '鍵',
      current: '現值',
      recommended: '建議值',
      same: '已經是這樣',
    },
    step: {
      temp_path_enabled: '啟用未完成目錄',
      temp_path: '未完成目錄',
      save_path: '完成目錄',
      auto_tmm_enabled: '自動 Torrent 管理',
      category_changed_tmm_enabled: '分類改變時跟著搬',
      web_ui_password: 'WebUI 帳密',
    },
    fix: {
      temp_path_enabled: '在 qBittorrent 的「選項 → 下載」勾選「保留未完成的 torrent 於」：',
      temp_path: '在「選項 → 下載」把未完成目錄設成 Berth 的 incomplete 根目錄：',
      save_path: '在「選項 → 下載」把預設儲存路徑設成 Berth 的 complete 根目錄：',
      auto_tmm_enabled: '在「選項 → 下載」把「預設 Torrent 管理模式」設成自動：',
      category_changed_tmm_enabled: '在「選項 → 下載」讓分類改變時套用新的儲存路徑：',
      web_ui_password: '在「選項 → Web UI」自己設定帳號與密碼：',
    },
    warning: {
      tempPath:
        '這台 qBittorrent 沒有啟用未完成目錄。不阻擋——但下載中的檔案會直接寫在完成目錄裡，Berth 比較難分辨哪些已經下載完。',
    },
    blocked: {
      tooOld:
        'qBittorrent {{version}} 的 Web API 低於 2.8.4，Berth 要用的端點在那之前不存在。升級到 4.4 以上再回來。',
      unreachable: '連不上這台 qBittorrent。位址、port 或容器狀態有問題。',
      upgrade: '升級 qBittorrent（套件內的話拉新的 image 再起一次）：',
    },
    apply: '套用這 {{keys}} 個鍵',
    applying: '套用中…',
    rerun: '重新檢查並套用',
    done: '這個泊位的事做完了。qBittorrent 的路徑與自動管理都是 Berth 要的樣子。',
    requestFailed: '請求沒跑完。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
  },
  source: {
    title: '接上抓取來源',
    lede: '索引站決定 Berth 找得到什麼，TMDB 決定它認得出什麼。兩個都可以之後再說。',
    skip: '之後再說',
    unreachable: '連不上套件內的 Prowlarr。可以先填自己的位址，或跳過這一步之後再補。',
    cutaway: {
      indexers: '索引站',
      kind: '接法',
      bundled: '套件內 Prowlarr',
      added: '已加入',
      tmdb: 'TMDB',
      credential: '憑證',
      endpoint: '測試打的端點',
    },
    kind: {
      prowlarr: 'Prowlarr',
      torznab: 'Torznab 端點',
    },
    indexers: {
      title: '預設公開索引站',
      lede: 'Berth 會把勾起來的站加進這台 Prowlarr。加之前 Prowlarr 會先連一次那個站，所以逐站都有結果——公開站有幾個連不上是常態，不影響其他站。',
      pick: '要加入哪些站',
      semiPrivate: '半私有站，可能需要帳號',
      apply: '加入這 {{sites}} 個站',
      applying: '加入中…',
      fix: '這個站 Prowlarr 連不上。可以在它自己的介面上手動加、換一個鏡像網址，或直接不勾它：',
      retryHint: '其他站不受影響。改好之後重按，已經加好的站不會被加第二次。',
      login: '替 Prowlarr 介面設登入',
      loginFix:
        '帳密沒設成功，Prowlarr 的介面仍然是免登入的。設完它會自行重啟，所以也可能只是還沒回來。可以在它自己的介面上設：',
    },
    existing: {
      title: '接入你自己的索引站',
      lede: 'Prowlarr 填它的位址與 API key；Jackett 或單站則填整條 Torznab 網址與它的 key。',
      kind: '接法',
      test: '測試連線',
      testing: '測試中…',
      fix: '確認位址、port 與 API key 都對，再確認那台服務從 Berth 這個容器連得到。',
      hint: {
        prowlarr: 'Prowlarr 的位址，例如 http://192.168.1.10:9696。API key 在它的「設定 → 一般」。',
        torznab:
          '整條 Torznab 網址。Jackett 的聚合網址是 /api/v2.0/indexers/all/results/torznab/api。',
      },
    },
    tmdb: {
      title: 'TMDB',
      lede: 'Berth 內建一把專案級憑證，什麼都不填也用得了。要用自己的就填在這裡，它會蓋過內建的那一把。',
      field: '你自己的 TMDB API key（選填）',
      placeholder: '留空就用內建的',
      hint: 'v3 的 API key 或 v4 的 read access token 都可以。',
      test: '測試 TMDB',
      testing: '測試中…',
      line: '驗證憑證',
      fix: '確認 key 沒有打錯，也確認這台機器連得到 api.themoviedb.org：',
      builtIn: 'Berth 內建的專案級憑證',
      overridden: '你自己填的 key',
      ownKeyLabel: '已覆寫',
      ownKey: '之後所有 TMDB 請求都會用你這一把 key，不再用內建的。',
    },
  },
  login: {
    code: 'BTH 0',
    title: '登船口',
    field: {
      username: '帳號',
      password: '密碼',
    },
    submit: '登入',
    submitting: '登入中…',
    source: 'Berth 沒有自己的密碼。登入用的是你的 Jellyfin 帳號，角色也由 Jellyfin 決定。',
    expiredChip: '已過期',
    expired: '工作階段已過期，請重新登入。',
    error: {
      refused: '帳號或密碼不對。',
      unavailable: '連不上 Jellyfin。Berth 的帳號來自它，它沒起來就沒有人登得進來。',
      unexpected: '登入沒有走完（HTTP {{status}}）。密碼不一定有錯——先看 Berth 自己的紀錄。',
    },
  },
  role: {
    admin: '管理員',
    user: '使用者',
  },
  nav: {
    settings: '設定',
    signOut: '登出',
    signingOut: '登出中…',
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
    warning: '警告',
    cancel: '取消',
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
    stage: {
      pre: 'Pre-berth',
      berth: 'Berth {{code}}',
    },
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
    continue: 'Go to Berth 1',
    waitingLabel: 'Waiting',
    waiting: '{{waited}} of {{window}} seconds',
    waitingHint: 'Containers are still starting. Berth keeps probing until the limit.',
    failed: 'The probe did not finish. The Berth backend may not be running — check it and retry.',
    empty: 'Not probed yet.',
    done: '{{count}} services decided',
  },
  service: {
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    prowlarr: 'Prowlarr',
  },
  status: {
    ok: 'Done',
    skipped: 'Already so',
    failed: 'Failed',
    running: 'Running',
    pending: 'Not run',
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
  jellyfin: {
    unreachable: 'Cannot read the state of this step. Check that the Berth backend is running.',
    cutaway: {
      sequence: 'What will happen',
      server: 'This Jellyfin',
      apiKey: 'API key',
      held: 'Held',
      absent: 'Not yet',
      libraries: 'Libraries',
      mergeVersions: 'MergeVersions',
      installed: 'Installed',
      notInstalled: 'Not installed',
    },
    step: {
      public_info: 'Confirm the startup wizard has not run',
      configuration: 'Language and metadata region',
      admin_user: 'Create the administrator from the Berth credentials',
      libraries: 'Create the Movies / TV / Anime libraries',
      remote_access: 'Enable remote access',
      complete: 'Finish the startup wizard',
      api_key: 'Create an API key for Berth',
      plugin: 'Install MergeVersions and restart',
      tasks: 'Record the two merge task Ids',
    },
    bundled: {
      title: 'Take this Jellyfin over',
      lede: 'This Jellyfin has not run its own startup wizard, so Berth can do all of it. Every step is safe to press again: the ones already in the right shape are marked "already so" and are not redone.',
      run: 'Start mooring',
      rerun: 'Run it again',
      retry: 'Retry the failed step',
      running: 'Running…',
      done: 'This berth is secured. Jellyfin has the Berth administrator, the three libraries and MergeVersions.',
      requestFailed:
        'The request did not finish. The Berth backend may not be running — check it and retry.',
    },
    existing: {
      title: 'Connect your Jellyfin',
      lede: 'This Jellyfin already ran its own startup wizard, so Berth only inspects it. It never creates libraries, never changes the options of your existing libraries, and never deletes anything.',
      username: 'Jellyfin administrator',
      password: 'Jellyfin administrator password',
      passwordHint: 'Used once to obtain an API key for Berth. It is not stored.',
      signIn: 'Sign in and create an API key',
      signInAgain: 'Sign in again',
      signingIn: 'Signing in…',
      requestFailed:
        'The request did not finish. Check the address and the Berth backend, then retry.',
    },
    libraries: {
      title: 'Libraries and paths',
      lede: 'Everything here is what Jellyfin itself reports. Existing paths are never touched — Berth only adds one more path to write into.',
      empty:
        'This Jellyfin has no libraries at all. Create one in Jellyfin and come back, so Berth has somewhere to write.',
      emptyLabel: 'No libraries',
      wired: 'Wired',
      unwired: 'Unassigned',
      paths: 'Paths',
      berthPath: 'Berth writes here',
      fetchers: 'Metadata sources',
      warningLabel: 'Warning',
      tvdb: 'This library fetches metadata from TVDB. Berth matches titles against TMDB for now, so season and episode numbers may disagree. Not blocking, but look here first when a match goes wrong.',
      willAdd: 'This path will be added',
      addPath: 'Add the Berth path',
      addConfirm: 'Confirm',
      adding: 'Adding…',
      addWarning:
        'Adds {{path}} to the library "{{library}}". Existing paths stay, no rescan is triggered, and watch history is unaffected.',
      addFailed:
        'The path was not added. The usual cause is that Berth and Jellyfin do not mount the same host directory at the same container path — Berth can create the directory but Jellyfin cannot see it. You can also add the path by hand under Jellyfin Libraries:',
    },
    plugin: {
      title: 'MergeVersions plugin',
      lede: 'With two files for the same episode Jellyfin shows two duplicate entries by default. This plugin merges them into one entry with several versions.',
      install: 'Install MergeVersions',
      confirm: 'Confirm and restart',
      installing: 'Installing…',
      warning:
        'Adds the danieladov plugin repository to your Jellyfin, installs MergeVersions, then restarts Jellyfin. Anyone watching is disconnected during the restart, usually for under a minute.',
      already: 'Version {{version}}; merge task Ids {{movies}} and {{episodes}} recorded.',
    },
    fix: {
      generic: 'Do this step by hand on your Jellyfin, then come back and retry.',
      public_info:
        'Check the Jellyfin container is running, then check the address and port were not changed:',
      configuration: "Set the language and metadata country in Jellyfin's own startup wizard:",
      admin_user:
        "Create the administrator in Jellyfin's own startup wizard, using the same credentials as step 1 here:",
      libraries:
        "Create the Movies, TV and Anime libraries by hand under Jellyfin's Libraries, with real-time monitoring off and Specials as the season-zero name:",
      remote_access: "Enable remote access in Jellyfin's startup wizard:",
      complete: "Finish Jellyfin's own startup wizard through to the last page:",
      api_key: "Create an API key named Berth under Jellyfin's API Keys:",
      plugin:
        "Add the manifest below under Jellyfin's Plugins → Repositories, install Merge Versions, then restart Jellyfin:",
      tasks:
        'Check MergeVersions is enabled and that Merge All Movies and Merge All Episodes appear under Scheduled Tasks:',
      retryHint:
        'Once you have done it by hand, press the button below — Berth only reruns the steps that are not finished.',
    },
  },
  qbittorrent: {
    title: 'Apply the recommended qBittorrent settings',
    unreachable: 'Cannot read the state of this step. Check that the Berth backend is running.',
    lede: {
      bundled:
        'This qBittorrent came with the bundle, so Berth writes its preferences directly. The five keys below are the ones Berth needs; only the ones that differ get written.',
      existing:
        'This qBittorrent is yours. Berth writes only the keys below — no other settings, and none of your existing torrents.',
    },
    cutaway: {
      server: 'This qBittorrent',
      webapi: 'Web API',
      password: 'WebUI password',
      willSet: 'Will be set to the step 1 credentials',
      diff: 'Keys that will be written',
      key: 'Key',
      current: 'Current',
      recommended: 'Recommended',
      same: 'Already set',
    },
    step: {
      temp_path_enabled: 'Keep incomplete downloads separate',
      temp_path: 'Incomplete folder',
      save_path: 'Completed folder',
      auto_tmm_enabled: 'Automatic torrent management',
      category_changed_tmm_enabled: 'Relocate when the category changes',
      web_ui_password: 'WebUI credentials',
    },
    fix: {
      temp_path_enabled: 'In qBittorrent, Options → Downloads, tick "Keep incomplete torrents in":',
      temp_path: "In Options → Downloads, point the incomplete folder at Berth's incomplete root:",
      save_path: "In Options → Downloads, set the default save path to Berth's completed root:",
      auto_tmm_enabled:
        'In Options → Downloads, set the default torrent management mode to Automatic:',
      category_changed_tmm_enabled:
        'In Options → Downloads, let a category change relocate the torrent:',
      web_ui_password: 'Set the username and password yourself under Options → Web UI:',
    },
    warning: {
      tempPath:
        'This qBittorrent does not keep incomplete downloads separate. Not a blocker — but partial files land in the completed folder, which makes "finished" harder to tell apart.',
    },
    blocked: {
      tooOld:
        'qBittorrent {{version}} speaks a Web API older than 2.8.4, and the endpoints Berth needs did not exist yet. Upgrade to 4.4 or newer and come back.',
      unreachable: 'Cannot reach this qBittorrent. Check the address, the port, or the container.',
      upgrade: 'Upgrade qBittorrent (for the bundled one, pull a new image and start it again):',
    },
    apply: 'Apply these {{keys}} keys',
    applying: 'Applying…',
    rerun: 'Check and apply again',
    done: "This berth is done. qBittorrent's paths and automatic management are what Berth needs.",
    requestFailed:
      'The request did not finish. Check that the Berth backend is running, then try again.',
  },
  source: {
    title: 'Connect a source',
    lede: 'Indexers decide what Berth can find; TMDB decides what it can recognise. Both can wait.',
    skip: 'Do this later',
    unreachable:
      'Cannot reach the bundled Prowlarr. Point Berth at your own instead, or skip this step and come back.',
    cutaway: {
      indexers: 'Indexers',
      kind: 'Connection',
      bundled: 'Bundled Prowlarr',
      added: 'Added',
      tmdb: 'TMDB',
      credential: 'Credential',
      endpoint: 'Endpoint the test calls',
    },
    kind: {
      prowlarr: 'Prowlarr',
      torznab: 'Torznab endpoint',
    },
    indexers: {
      title: 'Default public indexers',
      lede: 'Berth adds the ticked sites to this Prowlarr. Prowlarr connects to each site before saving it, so every site gets its own verdict — a few public sites being unreachable is normal and does not affect the rest.',
      pick: 'Which sites to add',
      semiPrivate: 'Semi-private; may need an account',
      apply: 'Add these {{sites}} sites',
      applying: 'Adding…',
      fix: 'Prowlarr could not reach this site. Add it by hand in Prowlarr, try another mirror, or leave it unticked:',
      login: 'Set the Prowlarr interface login',
      loginFix:
        'The credentials did not stick, so the Prowlarr interface is still open. Setting them restarts Prowlarr, so it may simply not be back yet. You can set them there yourself:',
      retryHint:
        'The other sites are unaffected. Press again after fixing it; sites already added are not added twice.',
    },
    existing: {
      title: 'Connect your own indexer',
      lede: 'For Prowlarr, give its address and API key. For Jackett or a single site, give the whole Torznab URL and its key.',
      kind: 'Connection',
      test: 'Test connection',
      testing: 'Testing…',
      fix: "Check the address, the port and the API key, then check that Berth's container can reach that service:",
      hint: {
        prowlarr:
          'The Prowlarr address, e.g. http://192.168.1.10:9696. Its API key is under Settings → General.',
        torznab:
          "The whole Torznab URL. Jackett's aggregate URL ends in /api/v2.0/indexers/all/results/torznab/api.",
      },
    },
    tmdb: {
      title: 'TMDB',
      lede: 'Berth ships a project credential, so this works with nothing filled in. Paste your own to override it.',
      field: 'Your own TMDB API key (optional)',
      placeholder: 'Leave empty to use the built-in one',
      hint: 'Either a v3 API key or a v4 read access token works.',
      test: 'Test TMDB',
      testing: 'Testing…',
      line: 'Verify the credential',
      fix: 'Check the key for typos, and check that this machine can reach api.themoviedb.org:',
      builtIn: "Berth's built-in project credential",
      overridden: 'Your own key',
      ownKeyLabel: 'Overridden',
      ownKey: 'Every TMDB request from now on uses your key instead of the built-in one.',
    },
  },
  login: {
    code: 'BTH 0',
    title: 'Gangway',
    field: {
      username: 'Username',
      password: 'Password',
    },
    submit: 'Sign in',
    submitting: 'Signing in…',
    source:
      'Berth has no passwords of its own. You sign in with your Jellyfin account, and Jellyfin decides your role.',
    expiredChip: 'Expired',
    expired: 'Your session expired. Sign in again.',
    error: {
      refused: 'That username and password do not match.',
      unavailable:
        'Cannot reach Jellyfin. Berth gets its accounts from it, so nobody can sign in until it is up.',
      unexpected:
        'Sign-in did not go through (HTTP {{status}}). Your password may well be fine — check the Berth log first.',
    },
  },
  role: {
    admin: 'Admin',
    user: 'User',
  },
  nav: {
    settings: 'Settings',
    signOut: 'Sign out',
    signingOut: 'Signing out…',
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
    warning: 'Warning',
    cancel: 'Cancel',
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

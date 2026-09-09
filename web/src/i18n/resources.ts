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
    waiting: '待靠泊',
  },
  setup: {
    title: '設定精靈',
    stage: {
      pre: '前置',
      berth: '泊位 {{code}}',
      final: '收尾',
    },
    step: '第 {{current}} 步，共 {{total}} 步',
    resumed: '進度已保留，關掉瀏覽器再回來會回到這一步。',
    exit: '回到 Berth',
    revisited:
      'Berth 已經設定好了。這裡改的是連線設定，不會重跑一次靠泊；每一步都可以只做你要改的那一個。',
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
    lede: '索引站決定 Berth 找得到什麼，TMDB 決定它認得出什麼。索引站可以之後再說，TMDB 不行。',
    skip: '之後再說',
    deferred: '之後再說',
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
      lede: 'Berth 不內建任何一把 API key，TMDB 的憑證要你自己申請。這一步是必填的：沒有它就沒有標題、季集與封面，探索、命名與入庫全部停擺。',
      required: '必填',
      held: '已取得',
      absent: '還沒填',
      whereLabel: '去哪裡拿',
      where:
        '在 themoviedb.org 註冊一個免費帳號，開「設定 → API」申請，用途選 Personal / Education，申請表要填一個網址與用途摘要。核發是即時的，不必等審核。現在就去申請也沒關係——精靈的進度已經存下來了，回來時還在這一步。',
      open: '開啟 TMDB 的 API 設定',
      blank: '這一步要一把 key 才走得下去。貼上你在 themoviedb.org 拿到的那一把再按一次。',
      field: '你的 TMDB API key',
      placeholder: '貼上 API key 或 read access token',
      hint: 'v3 的 API key（32 個十六進位字元）或 v4 的 read access token（很長的一串）都可以，貼哪一種都成立。',
      test: '測試 TMDB',
      testing: '測試中…',
      line: '驗證憑證',
      fix: '確認 key 沒有打錯，也確認這台機器連得到 api.themoviedb.org：',
    },
  },
  routes: {
    title: '媒體庫路徑',
    lede: {
      bundled:
        'Berth 替你建的三個媒體庫各成為一條 Route：下載完成後檔案硬鏈接到它的寫入目標。按下去會在 qBittorrent 建好分類，並實際鏈接一個檔案，確認三個容器看到的是同一個檔案系統。',
      existing:
        '勾選要交給 Berth 寫入的媒體庫，每個選一條寫入目標。舊路徑不會被動到——它們仍然唯讀，Berth 只往你選的那一條寫。',
    },
    empty:
      '這台 Jellyfin 一個媒體庫都沒有。先在 Jellyfin 建一個再回來，Berth 才有地方寫入。Berth 不會替你的伺服器建媒體庫。',
    unreachable: '讀不到媒體庫清單。Berth 後端可能沒在跑——確認容器狀態後重新整理。',
    building: '建立中…',
    build: '建立 {{count}} 條 Route 並檢查',
    requestFailed: '請求沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    cutaway: {
      paths: '路徑',
      libraryRoot: '媒體庫根目錄',
      completeRoot: 'complete 根目錄',
      count: 'Route 數',
      plan: '將建立',
      library: '媒體庫',
      target: '寫入目標',
      category: 'category',
    },
    picker: {
      title: '選擇媒體庫',
      lede: '一個媒體庫一條 Route。路徑是 Jellyfin 回報的，所以這裡用選的，不用打的。',
      target: '寫入目標',
      profile: '命名 profile',
      mixed: '混合',
      unsupported: 'Berth 只寫入電影與劇集類型的媒體庫，這一個跳過。',
      tvdb: '這個媒體庫掛了 TVDB 的 metadata fetcher。Berth 以 TMDB 為準，兩者的季集編號可能不同。',
      noPath: '這個媒體庫在 Jellyfin 上沒有任何路徑。',
      addBerthPath: '加入 Berth 路徑',
      adding: '加入中…',
      addHint: '在這個媒體庫加一條 {{path}}，舊路徑原地不動；加完就用它當寫入目標。',
    },
    profile: {
      standard: '標準',
      anime: '動漫',
    },
    health: {
      unknown: '尚未檢查',
      ok: '已繫上',
      failed: '阻擋',
    },
    check: {
      category: '建立 qBittorrent 分類',
      downloadPath: 'qBittorrent 的路徑 Berth 看得到',
      libraryPath: 'Jellyfin 的媒體庫路徑 Berth 看得到',
      probeVisible: 'Jellyfin 看得到 Berth 寫的檔案',
      hardlink: '硬鏈接與 inode 比對',
    },
    fix: {
      category:
        '同名的分類已經指到別的地方了。Berth 不會替你搬動它——開著 autoTMM 時改分類路徑會搬走該分類所有 torrent。到 qBittorrent 的分類設定改掉那條路徑，或先刪掉那個分類再重按。',
      berthMount:
        'berth 容器少了這條路徑的掛載：那個服務看得到，Berth 看不到。三個容器要把同一個宿主目錄掛在同一個容器路徑。改完 compose 之後跑 docker compose up -d：',
      jellyfinMount:
        'jellyfin 容器少了這條路徑的掛載：Berth 寫了一個檔案在那裡，Jellyfin 說它看不到。三個容器要把同一個宿主目錄掛在同一個容器路徑。改完 compose 之後跑 docker compose up -d：',
      hardlink:
        '鏈接不起來。complete 目錄與媒體庫目錄要在同一個檔案系統，容器裡的使用者也要寫得進去。',
      crossDevice:
        '這兩個目錄在 Berth 內是不同掛載（EXDEV）。硬鏈接跨不了掛載點——用一條掛載蓋住整個父目錄，不要 complete 與 library 各掛一條。網路磁碟、exFAT 隨身碟與 mergerfs 也做不到硬鏈接。',
    },
  },
  complete: {
    title: '完成設定',
    lede: '四個泊位都繫上了。按下完成之後精靈就關閉，之後要用 Jellyfin 帳號登入才進得來設定。',
    submit: '完成設定',
    completing: '完成中…',
    back: '回媒體庫路徑',
    failed: '寫不進去。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    signInHint: '完成後會回到首頁，那裡會請你用剛才建立的 Jellyfin 管理員帳號登入。',
    savePath: 'complete 目錄',
    skippedTitle: '跳過的步驟',
    cutaway: {
      title: '這一輪的結果',
      routes: 'Route 數',
      skipped: '跳過',
      nothing: '沒有',
    },
    skipped: {
      indexers: '索引站',
    },
    where: {
      indexers: '索引站還沒接。之後在「設定 → 來源」補上，補之前搜尋不到任何東西。',
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
    discover: '探索',
    health: '健康',
    settings: '設定',
    signOut: '登出',
    signingOut: '登出中…',
  },
  discover: {
    trending: '本週趨勢',
    popular: '熱門',
    results: '「{{query}}」的結果',
    tracked: '已追蹤',
    noArt: '無海報',
    empty: 'TMDB 這一輪什麼都沒回。過一小時快取到期後會再問一次。',
    off: '讀不到 Berth 後端。確認程序是否還在執行。',
    search: {
      label: '搜尋作品',
      placeholder: '劇名、片名，中文或英文',
      tooShort: '再打 {{count}} 個字以上就開始搜尋。',
      searching: '搜尋中…',
      count: '{{count}} 部作品',
      none: '沒有作品叫「{{query}}」。換個寫法，或試試原文標題。',
    },
    problem: {
      credential_missing:
        'Berth 還沒有 TMDB 憑證。它不內建任何一把，要你自己去 themoviedb.org 申請並填進設定精靈。',
      credential_rejected: 'TMDB 不接受這把憑證。它可能被撤銷了，或貼進來時少了幾個字。',
      unreachable: '連不上 TMDB。可能是這台機器沒有對外網路，或 TMDB 正在維護。',
      toSetup: '前往設定精靈',
      askAdmin: '請管理員到設定精靈補上 TMDB 憑證。',
      retry: '重試',
    },
    attribution: '本產品使用 TMDB 的 API，但未經 TMDB 認可或認證。',
  },
  health: {
    title: '健康',
    checking: '檢查中…',
    unreachable: '連不上 Berth 後端。確認程序是否還在執行。',
    interval: '每 {{minutes}} 分鐘自動檢查一次',
    lastChecked: '上次檢查',
    lastOk: '最後成功',
    never: '沒有紀錄',
    recheck: '立即重測',
    rechecking: '重測中…',
    recheckFailed: '重測沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    failures: '連續失敗 {{count}} 次',
    state: {
      ok: '已繫上',
      drift: '設定被改過',
      failed: '阻擋',
      unknown: '尚未檢查',
      unconfigured: '尚未接上',
    },
    routes: {
      title: '媒體庫路徑',
      count: '{{count}} 條 Route',
      expand: '展開檢查',
      collapse: '收起',
      empty: '還沒有 Route。在設定精靈的最後一個泊位建立它們，Berth 才有地方寫入。',
    },
    fix: {
      title: '修正',
      bundled:
        '這個服務是這套 compose 起的，所以先確認那個容器還在跑。三條指令的順序就是排查順序：還在嗎、把它起來、它自己說了什麼。',
      existing:
        '這是你自己的服務，Berth 只知道它現在回不出東西。位址或憑證變了的話回設定精靈重新填一次。',
      unconfigured: '這個服務還沒接上。到設定精靈接它——沒接上的話它負責的那件事一律不會發生。',
      drift:
        'Berth 的建議設定被改掉了（{{keys}}）。服務本身還在動，但下載路徑或自動管理一旦不對，入庫遲早會失敗。',
    },
    toSetup: '到設定精靈',
    toSettings: '到服務設定',
  },
  settings: {
    title: '服務設定',
    lede: '位址與憑證在設定精靈改。這一頁只有兩件事：重測連線，以及把被改掉的建議設定還原。',
    test: '測試連線',
    testing: '測試中…',
    testFailed: '測試沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    editHint: '改位址或憑證',
    drift: {
      title: 'qBittorrent 建議設定',
      clean: '五個建議鍵都還是建議值。',
      changed: '{{count}} 個鍵與建議值不同。',
      changedKey: '已改',
      key: '鍵',
      current: '現值',
      recommended: '建議值',
      restore: '還原建議設定',
      restoring: '還原中…',
      restoreFailed: '寫不進去。qBittorrent 可能不在了，或帳密變了——看上面那一項的原文。',
      unreachable: '連不上 qBittorrent，讀不到它現在的偏好。',
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
    waiting: 'Awaiting berth',
  },
  setup: {
    title: 'Setup wizard',
    stage: {
      pre: 'Pre-berth',
      berth: '{{code}}',
      final: 'Cast off',
    },
    step: 'Step {{current}} of {{total}}',
    resumed: 'Progress is saved. Close the browser and you come back to this step.',
    exit: 'Back to Berth',
    revisited:
      'Berth is already set up. This changes connection settings; it does not moor everything again, and each step does only what you ask it to.',
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
    lede: 'Indexers decide what Berth can find; TMDB decides what it can recognise. The indexer can wait; TMDB cannot.',
    skip: 'Do this later',
    deferred: 'Deferred',
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
      lede: 'Berth ships no API key of its own, so this credential has to be yours. It is required: without it there are no titles, seasons or artwork, and browsing, naming and importing all stop.',
      required: 'Required',
      held: 'Held',
      absent: 'Not set yet',
      whereLabel: 'Where to get one',
      where:
        'Sign up for a free account on themoviedb.org, then open Settings → API and request a key for Personal / Education use; the form asks for a URL and a short summary of what you are building. The key is issued immediately, with no review to wait for. Going to get one now is fine — the wizard keeps its progress and comes back to this step.',
      open: "Open TMDB's API settings",
      blank:
        'This step needs a key to go on. Paste the one you got from themoviedb.org and press again.',
      field: 'Your TMDB API key',
      placeholder: 'Paste an API key or a read access token',
      hint: 'Either a v3 API key (32 hex characters) or a v4 read access token (a long string) works — paste whichever you have.',
      test: 'Test TMDB',
      testing: 'Testing…',
      line: 'Verify the credential',
      fix: 'Check the key for typos, and check that this machine can reach api.themoviedb.org:',
    },
  },
  routes: {
    title: 'Library paths',
    lede: {
      bundled:
        'Each of the three libraries Berth created becomes a route: finished downloads are hard-linked into its write target. Pressing this creates the qBittorrent categories and links a real file, proving all three containers see one file system.',
      existing:
        'Tick the libraries Berth may write into and pick one write target for each. Your existing paths are left alone: they stay read-only, and Berth writes only to the path you pick.',
    },
    empty:
      'This Jellyfin has no libraries. Create one in Jellyfin and come back, so Berth has somewhere to write. Berth does not create libraries on your server.',
    unreachable:
      'Could not read the library list. The Berth backend may be down — check the container, then reload.',
    building: 'Building…',
    build: 'Build {{count}} routes and check',
    requestFailed:
      'The request did not finish. The Berth backend may be down — check the container and press again.',
    cutaway: {
      paths: 'Paths',
      libraryRoot: 'Library root',
      completeRoot: 'Complete root',
      count: 'Routes',
      plan: 'Will create',
      library: 'Library',
      target: 'Write target',
      category: 'Category',
    },
    picker: {
      title: 'Pick the libraries',
      lede: 'One route per library. The paths come from Jellyfin, so you pick one instead of typing it.',
      target: 'Write target',
      profile: 'Naming profile',
      mixed: 'Mixed',
      unsupported: 'Berth writes into movie and TV libraries only, so this one is skipped.',
      tvdb: 'This library has a TVDB metadata fetcher. Berth follows TMDB, and the two number seasons and episodes differently.',
      noPath: 'This library has no path on Jellyfin.',
      addBerthPath: 'Add a Berth path',
      adding: 'Adding…',
      addHint:
        'Adds {{path}} to this library. Your existing paths stay where they are, and the new one becomes the write target.',
    },
    profile: {
      standard: 'Standard',
      anime: 'Anime',
    },
    health: {
      unknown: 'Not checked',
      ok: 'Moored',
      failed: 'Blocked',
    },
    check: {
      category: 'Create the qBittorrent category',
      downloadPath: 'Berth sees the qBittorrent paths',
      libraryPath: 'Berth sees the Jellyfin library paths',
      probeVisible: 'Jellyfin sees the file Berth wrote',
      hardlink: 'Hard link and inode match',
    },
    fix: {
      category:
        'A category with that name already points somewhere else. Berth will not move it for you: with autoTMM on, changing a category path moves every torrent in it. Change the path in the qBittorrent category settings, or delete the category and press again.',
      berthMount:
        'The berth container is missing a mount for this path: the other service can see it and Berth cannot. All three containers must mount the same host directory at the same container path. After editing compose, run docker compose up -d:',
      jellyfinMount:
        'The jellyfin container is missing a mount for this path: Berth wrote a file there and Jellyfin says it cannot see it. All three containers must mount the same host directory at the same container path. After editing compose, run docker compose up -d:',
      hardlink:
        'The link failed. The complete directory and the library directory have to sit on one file system, and the container user has to be able to write there.',
      crossDevice:
        'Those two directories are separate mounts inside Berth (EXDEV). A hard link cannot cross a mount point: use one mount covering the whole parent directory instead of mounting complete and library separately. Network shares, exFAT drives and mergerfs cannot hard-link either.',
    },
  },
  complete: {
    title: 'Finish setup',
    lede: 'All four berths are moored. Finishing closes the wizard; after that you sign in with a Jellyfin account to reach the settings.',
    submit: 'Finish setup',
    completing: 'Finishing…',
    back: 'Back to library paths',
    failed: 'Could not save. The Berth backend may be down — check the container and press again.',
    signInHint:
      'You land on the home page, which asks you to sign in with the Jellyfin administrator you just created.',
    savePath: 'Complete directory',
    skippedTitle: 'Skipped steps',
    cutaway: {
      title: 'What this run produced',
      routes: 'Routes',
      skipped: 'Skipped',
      nothing: 'Nothing',
    },
    skipped: {
      indexers: 'Indexers',
    },
    where: {
      indexers:
        'No indexer yet. Add one under Settings → Source; until then searches return nothing.',
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
    discover: 'Discover',
    health: 'Health',
    settings: 'Settings',
    signOut: 'Sign out',
    signingOut: 'Signing out…',
  },
  discover: {
    trending: 'Trending this week',
    popular: 'Popular',
    results: 'Results for “{{query}}”',
    tracked: 'Tracked',
    noArt: 'NO ART',
    empty: 'TMDB returned nothing this round. Berth asks again once the hour-long cache expires.',
    off: 'Cannot reach the Berth backend. Check that the process is still running.',
    search: {
      label: 'Search titles',
      placeholder: 'A series or film, in any language',
      tooShort: 'Type {{count}} or more characters to search.',
      searching: 'Searching…',
      count: '{{count}} titles',
      none: 'Nothing here is called “{{query}}”. Try another spelling, or the original title.',
    },
    problem: {
      credential_missing:
        'Berth has no TMDB credential. It ships without one: get your own key at themoviedb.org and paste it into the setup wizard.',
      credential_rejected:
        'TMDB rejected this credential. It may have been revoked, or lost a few characters on the way in.',
      unreachable:
        'Cannot reach TMDB. Either this machine has no outbound network, or TMDB is down.',
      toSetup: 'Open the setup wizard',
      askAdmin: 'Ask an administrator to add the TMDB credential in the setup wizard.',
      retry: 'Retry',
    },
    attribution: 'This product uses the TMDB API but is not endorsed or certified by TMDB.',
  },
  health: {
    title: 'Health',
    checking: 'Checking…',
    unreachable: 'Cannot reach the Berth backend. Check that the process is still running.',
    interval: 'Checked automatically every {{minutes}} min',
    lastChecked: 'Last checked',
    lastOk: 'Last success',
    never: 'No record',
    recheck: 'Check now',
    rechecking: 'Checking…',
    recheckFailed:
      'The check did not go through. The Berth backend may be down — check the container, then try again.',
    failures: '{{count}} consecutive failures',
    state: {
      ok: 'Moored',
      drift: 'Settings changed',
      failed: 'Blocked',
      unknown: 'Not checked',
      unconfigured: 'Not connected',
    },
    routes: {
      title: 'Library paths',
      count: '{{count}} routes',
      expand: 'Show checks',
      collapse: 'Hide',
      empty:
        'No routes yet. Create them in the last berth of the setup wizard — until then Berth has nowhere to write.',
    },
    fix: {
      title: 'Fix',
      bundled:
        'This service comes from the bundled compose file, so start by checking that its container is still running. The three commands are in triage order: is it there, bring it up, what did it say.',
      existing:
        'This is your own service, and all Berth knows is that it stopped answering. If its address or credentials changed, fill them in again in the setup wizard.',
      unconfigured:
        'This service is not connected yet. Connect it in the setup wizard — until then, whatever it is responsible for simply will not happen.',
      drift:
        "Berth's recommended settings were changed ({{keys}}). The service itself is still running, but once the download paths or automatic management are wrong, imports will fail sooner or later.",
    },
    toSetup: 'Open the setup wizard',
    toSettings: 'Open service settings',
  },
  settings: {
    title: 'Service settings',
    lede: 'Addresses and credentials are edited in the setup wizard. This page does two things: re-test a connection, and restore recommended settings that were changed.',
    test: 'Test connection',
    testing: 'Testing…',
    testFailed:
      'The test did not go through. The Berth backend may be down — check the container, then try again.',
    editHint: 'Change address or credentials',
    drift: {
      title: 'qBittorrent recommended settings',
      clean: 'All five recommended keys still hold their recommended values.',
      changed: '{{count}} keys differ from the recommended values.',
      changedKey: 'changed',
      key: 'Key',
      current: 'Current',
      recommended: 'Recommended',
      restore: 'Restore recommended settings',
      restoring: 'Restoring…',
      restoreFailed:
        'Could not write them. qBittorrent may be gone, or its credentials changed — read the raw message on that check above.',
      unreachable: 'Cannot reach qBittorrent, so its current preferences are unknown.',
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

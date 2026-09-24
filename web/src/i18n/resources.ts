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
    done_one: '{{count}} 個服務已判定',
    done_other: '{{count}} 個服務已判定',
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
    ip_banned: '把 Berth 這台的 IP 封了（連續登入失敗）',
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
    tmdb: 'TMDB',
    verified: '已驗證',
    unverified: '待驗證',
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
    },
    version: {
      label: '版本太舊',
      current: '這台 Jellyfin 是 {{version}}，Berth 需要 12.0 以上。',
      why: 'Jellyfin 12.0 起同一集的多個版本由它自己合併成一個條目；10.x 要靠第三方插件，而那個插件在 12 上是空跑，還會跨媒體庫誤併。所以 Berth 只支援 12 以上。（12.0 就是原本的 10.12，只是拿掉了版號前面的 10。）',
      upgrade:
        '升級前：先把 Jellyfin 的 /config 完整備份 —— 12 改了資料庫，降不回去，只能還原備份；再移除第三方插件，10.11 的插件在 12 載入不了。升級後：完整掃描一次媒體庫，自動分組的版本才會回來。',
    },
    step: {
      public_info: '確認版本與初始精靈還沒跑過',
      configuration: '語言與 metadata 地區',
      admin_user: '以 Berth 的帳密建立管理員',
      libraries: '建立 Movies / TV / Anime 三個媒體庫',
      remote_access: '開啟遠端存取',
      complete: '結束初始精靈',
      api_key: '建立 Berth 專用的 API key',
    },
    bundled: {
      title: '接手這台 Jellyfin',
      lede: '這台 Jellyfin 還沒跑過自己的初始精靈，所以 Berth 可以全部代辦。每一步都可以重按：已經對的那幾步會標成「已經是這樣」，不會做第二次。',
      run: '開始靠泊',
      rerun: '重新跑一次',
      retry: '重試失敗的那一步',
      running: '進行中…',
      done: '這個泊位的事做完了。Jellyfin 有 Berth 管理員、三個媒體庫與一把 Berth 專用的 API key。',
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
    fix: {
      generic: '在你的 Jellyfin 上手動做這一步，然後回來重試。',
      public_info: '確認 Jellyfin 容器活著、版本是 12.0 以上，再確認位址與 port 沒有被改掉：',
      configuration: '在 Jellyfin 自己的初始精靈把語言設成繁體中文、地區設成台灣：',
      admin_user: '在 Jellyfin 自己的初始精靈建立管理員，帳密要與這裡的第 1 步一致：',
      libraries:
        '在 Jellyfin 的「媒體庫」手動建立 Movies、TV、Anime 三個媒體庫，關掉即時監控、Specials 顯示名稱填 Specials：',
      remote_access: '在 Jellyfin 的初始精靈開啟遠端存取：',
      complete: '在 Jellyfin 自己的初始精靈按到最後一頁完成它：',
      api_key: '在 Jellyfin 的「API 金鑰」建立一把名為 Berth 的金鑰：',
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
    build_one: '建立 {{count}} 條 Route 並檢查',
    build_other: '建立 {{count}} 條 Route 並檢查',
    recheck_one: '重新檢查 {{count}} 條 Route',
    recheck_other: '重新檢查 {{count}} 條 Route',
    requestFailed: '請求沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    routeMissing:
      '這一步順便重新檢查了既有的 Route，其中一條在途中被刪掉了（多半是另一個分頁）。重新整理這一步，剩下的會再檢查一次。',
    cutaway: {
      paths: '路徑',
      libraryRoot: '媒體庫根目錄',
      completeRoot: 'complete 根目錄',
      count: '這一輪要建的 Route',
      plan: '將建立',
      library: '媒體庫',
      target: '寫入目標',
      category: '分類',
    },
    picker: {
      title: '選擇媒體庫',
      lede: '一個媒體庫一條 Route。路徑是 Jellyfin 回報的，所以這裡用選的，不用打的。',
      target: '寫入目標',
      mixed: '混合',
      unsupported: 'Berth 只寫入電影與劇集類型的媒體庫，這一個跳過。',
      tvdb: '這個媒體庫掛了 TVDB 的 metadata fetcher。Berth 以 TMDB 為準，兩者的季集編號可能不同。',
      noPath: '這個媒體庫在 Jellyfin 上沒有任何路徑。',
      routed:
        '已經有 Route 了：精靈只新增，不改也不刪它。選錯了就用下面那一條的刪除；精靈跑完之後在「設定 → 媒體庫路徑」管理。',
      addBerthPath: '加入 Berth 路徑',
      adding: '加入中…',
      addHint: '在這個媒體庫加一條 {{path}}，舊路徑原地不動；加完就用它當寫入目標。',
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
    needTmdb:
      '第 6 步還沒完成：TMDB 要一把測得過的 key。沒有它，探索、季集快照與命名全部停擺，所以這一步不能跳。',
    needRoutes: '第 7 步還沒完成：每一條 Route 的五條纜繩都要綠燈。紅著的那一條，送單一定失敗。',
    unfinished: '還有一步沒做完，但這一頁看不出是哪一步。回上一步逐格看一次，紅的那一格就是。',
    fixTmdb: '回去填 TMDB key',
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
    label: '主要導覽',
    skip: '跳到內容',
    discover: '探索',
    inventory: '媒體庫',
    jobs: '下載',
    issues: '待處理',
    review: '審核',
    health: '健康',
    settings: '設定',
    signOut: '登出',
    signingOut: '登出中…',
  },
  discover: {
    trending: '本週趨勢',
    popular: '熱門',
    results: '「{{query}}」的結果',
    noArt: '無海報',
    // Berth 曾為這部作品下載、訂閱或入庫過（`CONTEXT.md` 的 Tracked Media）。
    tracked: '已下載過',
    empty: 'TMDB 這一輪什麼都沒回。過一小時快取到期後會再問一次。',
    off: '讀不到 Berth 後端。確認程序是否還在執行。',
    search: {
      label: '搜尋作品',
      placeholder: '劇名、片名，中文或英文',
      tooShort: '再打 {{min}} 個字以上就開始搜尋。',
      searching: '搜尋中…',
      // 中文沒有單複數，兩個變體同字；`count_one` 存在只是為了讓兩個語言的鍵樹一致
      // （`Translations<typeof zhHant>` 要求形狀相同），實際永遠選不到它。
      count_one: '{{count}} 部作品',
      count_other: '{{count}} 部作品',
      none: '沒有作品叫「{{query}}」。換個寫法，或試試原文標題。',
      back: '回到趨勢',
    },
    attribution: '本產品使用 TMDB 的 API，但未經 TMDB 認可或認證。',
    tmdbLogo: 'TMDB 標誌',
  },
  // 首頁與媒體庫頁上方的兩列（M1.5 票 07）。資料原樣來自 Jellyfin，名稱不是文案。
  watching: {
    resume: '繼續觀看',
    nextUp: '下一集',
    count_one: '{{count}} 項',
    count_other: '{{count}} 項',
    showAll_one: '全部 {{count}} 項',
    showAll_other: '全部 {{count}} 項',
    showFewer: '收起',
    // 媒體庫頁收起來的兩列（M2 票 14）：一行、就地展開。
    carryOn_one: '接著看 {{count}} 項',
    carryOn_other: '接著看 {{count}} 項',
    // 16:9 的那一塊：這裡沒有海報可說。
    noArt: '無圖',
    down: '問不到 Jellyfin，繼續觀看與下一集暫時看不到。',
    retry: '重試',
    // 媒體庫頁翻頁或篩選時那兩列收起（票 13）：說得出它們去了哪裡。
    elsewhere: '繼續觀看與下一集只列在第 1 頁、沒有篩選的時候。',
    toFirst: '到第 1 頁看',
  },
  // 媒體庫頁（票 13、`.scratch/m1/library-shape.md`）。作品標題與 Route 名字不是文案，原樣顯示。
  inventory: {
    title: '媒體庫',
    // 切換列的名字：這位使用者在 Jellyfin 看得到的媒體庫（M1.5 票 03）。
    libraries: '媒體庫',
    filters: '篩選',
    filter: {
      all: '全部',
      review_one: '待審 {{count}}',
      review_other: '待審 {{count}}',
      unmatched_one: '對不到 {{count}}',
      unmatched_other: '對不到 {{count}}',
    },
    // 「待審」「對不到」篩出來的清單（M2 票 14）：審核佇列在這個媒體庫上的子集，一列一件事。
    queue: {
      review: '待審',
      unmatched: '對不到',
      rest_one: '審核佇列裡還有 {{count}} 件',
      rest_other: '審核佇列裡還有 {{count}} 件',
    },
    // 排序與類型、年份篩選（票 06）。選項照 jellyfin-web 的排序選單，兩種媒體庫各開哪幾個由後端說。
    sort: {
      label: '排序',
      order: '方向',
      Ascending: '遞增',
      Descending: '遞減',
      by: {
        SortName: '名稱',
        Random: '隨機',
        CommunityRating: '社群評分',
        CriticRating: '影評評分',
        DateCreated: '加入日期',
        DateLastContentAdded: '新集加入',
        SeriesDatePlayed: '最近看過',
        DatePlayed: '最近看過',
        OfficialRating: '分級',
        PlayCount: '播放次數',
        PremiereDate: '發行日期',
        Runtime: '片長',
      },
    },
    narrow: {
      genres: '類型',
      years: '年份',
      // 看得見的是數字，聽得見的是這一句。
      chosen_one: '已選 {{count}} 個',
      chosen_other: '已選 {{count}} 個',
      loading: '讀取中…',
      none: {
        genres: '這個媒體庫的作品沒有類型資料。',
        years: '這個媒體庫的作品沒有年份資料。',
      },
      failed: '讀不到這個媒體庫的篩選選項。',
      retry: '重試',
      clear: {
        genres: '清除類型',
        years: '清除年份',
      },
      // 篩類型或年份之後一部都沒有：空的是篩選的結果，不是媒體庫本身。
      nothing: '這個媒體庫沒有符合篩選的作品。',
      listed: {
        genres: '類型：{{list}}',
        years: '年份：{{list}}',
        q: '名字含「{{q}}」',
      },
      clearBoth: '清除類型與年份',
      clearSearch: '清除搜尋',
    },
    // 牆上按名字找（M2 票 14）：Jellyfin 的 `searchTerm`，名字裡的一段。
    search: {
      label: '按名字找',
    },
    showing_one: '顯示 {{count}} 件',
    showing_other: '顯示 {{count}} 件',
    // Berth 經手、Jellyfin 還沒有的作品。不叫「在路上」：失敗的、Jellyfin 找不到的也在這裡。
    notInJellyfin: '還沒進 Jellyfin',
    notInJellyfinCount_one: '{{count}} 部作品還沒進 Jellyfin',
    notInJellyfinCount_other: '{{count}} 部作品還沒進 Jellyfin',
    pages: '分頁',
    pagesEnd: '牆底的分頁',
    previous: '上一頁',
    next: '下一頁',
    // 看得見的是「1–50 / 523」，聽得見的是這一句。
    range: '第 {{first}}–{{last}} 部，共 {{total}} 部',
    rangeBeyond: '這一頁超出範圍，共 {{total}} 部',
    // 依序取第一個成立的（`InventoryStatus`）：需要人的那一件排前面。
    status: {
      failed: '失敗',
      review: '待審',
      downloading: '下載中',
      complete: '已入庫',
      partial: '部分',
      empty: '沒有檔案',
    },
    // 分母是已經播出的正片，S00 不算。
    episodes: '{{imported}} / {{aired}} 集入庫',
    versions_one: '{{count}} 個版本',
    versions_other: '{{count}} 個版本',
    // 這位使用者在 Jellyfin 看到哪了（票 05）。一行只說一件事，判定在後端（`services/watch.py`）。
    watch: {
      played: '已看',
      progress: '看到 {{progress}}%',
      // 沒開始看的劇也說（jellyfin-web 的計數徽章）。
      unplayed_one: '剩 {{count}} 集沒看',
      unplayed_other: '剩 {{count}} 集沒看',
      markPlayed: '標為已看',
      markUnplayed: '標為未看',
      pending: '寫入中…',
      named: '{{action}}：{{subject}}',
      // 寫入成功之後唸出來（票 11 的 audit，WCAG 2.1.3）。焦點這時已經回到那一顆鍵上，
      // 而它的名字是「剛剛換過的」——螢幕閱讀器不會為已經聚焦的元素重念新名字，所以要自己說。
      donePlayed: '已標為已看。',
      doneUnplayed: '已標為未看。',
      // 標為未看復原不了（研究 §5）：說清楚清掉的是什麼、範圍多大。
      warningMovie: '會清掉你看這部片的觀看次數與最後觀看時間，清掉就找不回來。',
      warningSeries:
        '會清掉你看這部劇每一集的觀看次數與最後觀看時間，之前單獨看過的集也一起清掉，清掉就找不回來。',
      warningEpisode: '會清掉你看這一集的觀看次數與最後觀看時間，清掉就找不回來。',
      // 標為已看也會清掉東西（M1.5 票 08 使用者拍板）：看到一半的位置歸零。
      warningProgress: '會清掉你看到 {{progress}}% 的位置，清掉就找不回來。',
      // 劇集的觀看紀錄看不出底下有沒有看到一半的集，所以一律說。
      warningSeriesPlayed: '每一集都會標為已看，看到一半的集位置也會歸零，清掉就找不回來。',
      refused: {
        item_not_visible: '你在 Jellyfin 看不到這部作品，沒有寫入。',
        jellyfin_unreachable:
          'Berth 問不到 Jellyfin，沒有寫入。到健康頁確認 Jellyfin 還在，再按一次。',
        other: '沒有寫入。Berth 自己的 API 沒有回應，先確認它還活著，再按一次。',
      },
    },
    jellyfin: {
      open: '在 Jellyfin 開啟',
      openNamed: '在 Jellyfin 開啟：{{title}}（開新分頁）',
      // 整格是一條開 Jellyfin 的連結時（繼續觀看與下一集、集卡）：名字是那一集或那一部，後面說會開新分頁。
      itemNewTab: '{{name}}（開新分頁）',
      // 看不見的那一半：連結會開新分頁。
      newTab: '（開新分頁）',
      searching: 'Jellyfin 還在掃描',
      lost: 'Jellyfin 找不到它',
      noAddress: '不知道 Jellyfin 開在哪裡',
      downLabel: '問不到 Jellyfin',
      down: 'Berth 問不到 Jellyfin，而媒體庫要靠它才知道你看得到哪些、裡面有什麼。',
      retry: '重試',
      toHealth: '看健康頁',
    },
    empty: {
      noLibraries: '你在 Jellyfin 看得到的媒體庫裡，沒有電影或劇集媒體庫。',
      askAdmin: '請管理員在 Jellyfin 開放媒體庫給你。',
      openJellyfin: '到 Jellyfin 的媒體庫設定',
      library: '「{{library}}」還沒有任何作品。',
      toDiscover: '回探索頁',
      page: '這一頁沒有作品。',
      toFirstPage: '回第 1 頁',
      review: '這個媒體庫沒有待審核的下載。',
      unmatched: '這個媒體庫沒有對不到的檔案。',
      showAll: '顯示全部',
      // 沒有權限與不存在是同一句話：分得出來就是在告訴人那個媒體庫存在。
      unknown: '找不到這個媒體庫，或你沒有權限看它。',
      toFirst: '看「{{library}}」',
    },
    off: '讀不到媒體庫。Berth 自己的 API 沒有回應，先確認它還活著。',
  },
  media: {
    // 身分帶那一行識別值（M1.5 票 08：五列剖面收成一行）。日期與 TMDB id 是值，不是文案。
    aired: '首播 {{date}}',
    released: '上映 {{date}}',
    tmdbId: 'TMDB {{id}}',
    // 現在它跟著 TMDB 的標題走，所以說的是「將會是」；定下來是送單那一刻的事。
    folderPreview: '資料夾將會是',
    // `user` 碰到停在待審核的下載只能等（brief §11、M2 票 06）。這一句只畫給他看。
    awaitingReview_one: '這部作品有 {{count}} 筆下載停在待審核，等管理員審核。',
    awaitingReview_other: '這部作品有 {{count}} 筆下載停在待審核，等管理員審核。',
    folderNote: '第一次送單成功那一刻這串字就定下來，之後 TMDB 改標題也不會動它。',
    // 定下來之後說的是「就是」，不是「將會是」（票 09）。
    folderFrozen: '資料夾是',
    folderFrozenNote: '這串字在第一次送單成功時定下來了，TMDB 改標題也不會動它。',
    tracked: '已下載過',
    // Berth 的季表：TMDB 的季集與它們的入庫狀態（上面觀看區的季是 Jellyfin 的）。
    seasons: '季集與入庫',
    backToDiscover: '回探索頁',
    stale: '快照是舊的',
    fetchedAt: '快照抓取於',
    refresh: '立即重抓',
    refreshing: '重抓中…',
    minutes_one: '{{count}} 分鐘',
    minutes_other: '{{count}} 分鐘',
    // 表格裡的緊湊寫法。同一個概念兩種長度，不是同一個字串硬塞兩個地方。
    minutesShort_one: '{{count}} 分',
    minutesShort_other: '{{count}} 分',
    season: {
      count_one: '{{count}} 季',
      count_other: '{{count}} 季',
      empty: 'TMDB 還沒有這一季的集數。開播之後會補上。',
      film: '電影沒有季集。',
      none: 'TMDB 上這部作品還沒有任何一季。',
      // 季表工具列的「只看缺集」（M1.5 票 09）。缺＝已播出、沒有任何下載在處理；卡住與未播出不算。
      missingOnly: '只看缺集',
      // 這一頁有四套集數（M2 票 14，M1.5 critique P3）：季表說自己是哪一套，觀看區在時連它一起說。
      numbering: '季與集照 TMDB 的編號，入庫的檔名也照這一份。',
      numberingWatched:
        '季與集照 TMDB 的編號，入庫的檔名也照這一份。上面「觀看」的季與集是 Jellyfin 的，兩邊的編號可能不同。',
      missingTotal_one: '共缺 {{count}} 集',
      missingTotal_other: '共缺 {{count}} 集',
      noneMissingAnywhere: '這部作品沒有缺集',
      missing_one: '缺 {{count}} 集',
      missing_other: '缺 {{count}} 集',
      noneMissing: '沒有缺集',
      noneMissingHere: '這一季沒有缺集。',
      // 缺集一鍵搜（M1.5 票 10）：查詢由後端依缺的季集產生，結果畫在上面的搜尋區塊裡。
      searchMissing: '搜這部作品缺的集',
      searchMissingSeason: '搜 {{season}} 缺的集',
    },
    episode: {
      count_one: '{{count}} 集',
      count_other: '{{count}} 集',
      number: '集',
      name: '標題',
      // 絕對編號：整部作品從第一集數到現在的序位。字幕組常常用它編號。
      absolute: '絕對',
      runtime: '片長',
      airDate: '播出',
      caption: '{{season}} 的每一集',
      // 窄版收進集名底下那一行（票 13）。
      runtimeValue: '片長 {{value}}',
      airDateValue: '播出 {{value}}',
      // 這一集在媒體庫裡的樣子（票 13，使用者拍板五種）。
      inLibrary: '入庫',
      state: {
        imported: '已入庫',
        downloading: '下載中',
        stuck: '卡住',
        missing: '缺',
        unaired: '未播出',
      },
    },
    // 檔案與版本（票 13）。路徑、Tags 與版本名是機器字串，原樣顯示。
    files: {
      title: '檔案與版本',
      count_one: '{{count}} 個檔案',
      count_other: '{{count}} 個檔案',
      // 區塊抬頭那個數字給螢幕閱讀器聽的說法。
      total_one: '共 {{count}} 個檔案',
      total_other: '共 {{count}} 個檔案',
      none: '還沒有任何檔案入庫。',
      special: '特別篇',
      // 逐檔列收起來的那兩行（M1.5 票 09b）：沒有欄頭時一串路徑說不出自己是目標還是來源。
      tags: 'Tags',
      target: '目標',
      action: {
        import: '正片',
        extra: '特典',
        subtitle: '字幕',
        skip: '略過',
        unmatched: '對不到',
        review: '待審',
      },
      ledger: {
        label: '帳本',
        ok: '對得上',
        // 一組檔案的摘要（M1.5 票 09）。
        allOk: '帳本對得上',
        off_one: '{{count}} 個帳本對不上',
        off_other: '{{count}} 個帳本對不上',
        target_missing: '媒體庫裡的檔案不見了',
        source_missing: 'complete 裡的來源不見了',
        inode_mismatch: '兩邊不再是同一個 inode',
        unlinked: '刪除時從媒體庫移除了',
      },
      jellyfin: {
        found: 'Jellyfin 已收錄',
        searching: 'Jellyfin 還在掃描，下一次查詢',
        // 一組檔案的摘要，只算正片（M1.5 票 09）。
        foundCount_one: 'Jellyfin 已收錄 {{count}}',
        foundCount_other: 'Jellyfin 已收錄 {{count}}',
        searchingCount_one: 'Jellyfin 掃描中 {{count}}',
        searchingCount_other: 'Jellyfin 掃描中 {{count}}',
        lostCount_one: 'Jellyfin 找不到 {{count}}',
        lostCount_other: 'Jellyfin 找不到 {{count}}',
        lost_one: 'Jellyfin 試了 {{count}} 次都沒找到',
        lost_other: 'Jellyfin 試了 {{count}} 次都沒找到',
      },
      versions: {
        title: '多版本並存',
        noneTv: '每一集都只有一個版本。',
        noneMovie: '這部電影只有一個版本。',
        note: '同一集的這幾個版本在 Jellyfin 裡是同一個條目的版本選單。選單上的名字與先後順序由 Jellyfin 決定，這裡顯示的就是它回報的那一串。',
        pending: 'Jellyfin 還沒收錄的版本沒有名字，上面顯示的是檔名裡的 tags。',
      },
      unmatched: {
        title: '對不到的檔案',
        note: '解析器對不到任何一集，所以這些檔案留在 complete 原位，不入庫。可以指派到某一集、標記為特典或忽略。',
        // 那一份計劃還在等審核：這時候改它是審核佇列的事。
        pending: '這筆下載的計劃還在等審核，到審核佇列決定。',
        toJobs: '看下載列表',
      },
    },
    route: {
      label: '入庫到',
      none: '尚未指定',
      toSetup: '到設定精靈建 Route',
      askAdmin: '請管理員建一條收得下它的 Route。',
      missing: {
        tv: '還沒有任何一條收劇集的 Route。沒有它，下載完了也沒有地方可以入庫。',
        movie: '還沒有任何一條收電影的 Route。沒有它，下載完了也沒有地方可以入庫。',
      },
    },
  },
  // Media 詳情的觀看區（M1.5 票 08、`.scratch/m1.5/media-detail-shape.md`）。季名與集名是 Jellyfin 的，
  // 不是文案。主按鈕開 Jellyfin 那一集的詳細頁——Jellyfin 沒有直接開始播放的網址（研究 §8）。
  watch: {
    title: '觀看',
    resume: '繼續看 {{code}}',
    next: '看下一集 {{code}}',
    first: '從 {{code}} 開始看',
    film: '在 Jellyfin 看',
    filmResume: '繼續看',
    open: '在 Jellyfin 開啟',
    allWatched: '全部看完了',
    seasons: '季',
    chipResume: '繼續看',
    chipNext: '下一集',
    noSeasons: 'Jellyfin 還沒有這部作品的集。',
    emptySeason: '這一季在 Jellyfin 還沒有集。',
    failed: '這一季的集讀不出來。',
    retry: '重試',
    down: '問不到 Jellyfin，觀看區暫時看不到。',
  },
  // 索引站搜尋與結果表（票 08）。發佈名、站名與 Tags token 不是文案——它們來自索引站
  // 與 brief §6.8 的詞彙表，原樣顯示。
  search: {
    title: '搜尋 torrent',
    keyword: '關鍵字',
    keywordPlaceholder: '留空就用這部作品的各個名字',
    // 從季表按進來之後（票 13）：留空問的是缺的那幾集，不是作品名。
    keywordPlaceholderMissing: '留空就問缺的那幾集',
    submit: '搜尋',
    submitting: '搜尋中…',
    willAsk: 'Berth 會拿這幾個名字各問一次：',
    willAskTyped: 'Berth 只會問這一個：',
    // 從季表按進來的那一種（M1.5 票 10）：問的是缺的那幾集，關鍵字一樣由後端給。
    willAskMissing: '這部作品缺的那幾集，Berth 會這樣問：',
    willAskMissingSeason: '{{season}} 缺的那幾集，Berth 會這樣問：',
    missingOff: '改回作品名搜尋',
    // 搜尋結束之後，有回應的纜繩收成這一行（M1.5 票 08：全綠的纜繩曾佔掉 311px）。
    answeredAll_one: '{{count}} 個關鍵字都有回應',
    answeredAll_other: '{{count}} 個關鍵字都有回應',
    answeredRest_one: '其餘 {{count}} 個關鍵字有回應',
    answeredRest_other: '其餘 {{count}} 個關鍵字有回應',
    slow: '索引站要現場去連它認得的每一個追蹤站，這通常要一分鐘左右。',
    count_one: '共 {{count}} 筆',
    count_other: '共 {{count}} 筆',
    countCapped: '共 {{total}} 筆 · 逐站取了 {{shown}} 筆',
    empty:
      '這幾個關鍵字在你的索引站上沒有東西。換個寫法自己打一次，或改天再搜——公開站的片源是會變的。',
    // 索引站對搜不到的關鍵字常常回它自己的熱門清單（實測 The Pirate Bay），所以
    // 「什麼都沒回」與「回了一堆但沒有一筆是這部作品」是兩件事，下一步也不同。
    onlyOthers_one:
      '索引站回了 {{count}} 筆，但沒有一筆對得上這部作品的名字。自己打一個關鍵字試試。',
    onlyOthers_other:
      '索引站回了 {{count}} 筆，但沒有一筆對得上這部作品的名字。自己打一個關鍵字試試。',
    discarded_one: '另有 {{count}} 筆名字對不上這部作品，已經略過。',
    discarded_other: '另有 {{count}} 筆名字對不上這部作品，已經略過。',
    off: '搜尋沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
    announce_one: '找到 {{count}} 筆，{{failed}} 個關鍵字沒問到。',
    announce_other: '找到 {{count}} 筆，{{failed}} 個關鍵字沒問到。',
    column: {
      title: '發佈名',
      size: '大小',
      seeders: '做種',
      indexer: '來源',
      estimate: '預估',
    },
    // 窄版把另外四欄收成一行，做種要自己帶標籤才知道那個數字是什麼。
    seedersInline_one: '做種 {{value}}',
    seedersInline_other: '做種 {{value}}',
    sort: {
      label: '排序',
    },
    estimate: {
      wholeSeason: '全季',
      unknown: '判斷不出來',
      movie: '電影',
    },
    // 五種樣子，五種下一步。索引站是精靈裡唯一可以跳過的一步，所以「沒接」不是失敗。
    problem: {
      not_configured: {
        label: '還沒接',
        body: '設定精靈的第 5 步跳過了索引站，所以 Berth 沒有地方可以搜。接上 Prowlarr 或任意 Torznab 端點之後這一區塊就會動。',
      },
      no_query: {
        label: '無法搜尋',
        body: 'Berth 還沒有這部作品的 TMDB 快照，所以不知道要拿什麼名字去問。到上面按「立即重抓」，或自己打一個關鍵字。',
      },
      no_search: {
        label: '不提供搜尋',
        body: '這個 Torznab 端點回報它不提供搜尋。位址與 key 都對，但它做不了這件事——換一個端點。',
      },
      credential_rejected: {
        label: '憑證被拒',
        body: '索引站不接受這把 API key。它可能被換掉了，或貼進來時少了幾個字。',
      },
      unreachable: {
        label: '連不上',
        body: '連不上索引站。可能是那個容器沒起來，或位址填錯了。',
      },
      toSetup: '前往設定精靈',
      askAdmin: '請管理員到設定精靈接上索引站。',
    },
  },
  // 下載列表頁與送單（票 09、`.scratch/m1/jobs-shape.md`）。發佈名、hash、路徑、category
  // 與 `client_state` 不是文案——它們是機器字串，原樣顯示（The Machine String Rule）。
  issues: {
    title: '待處理',
    count_one: '{{count}} 件',
    count_other: '{{count}} 件',
    // 這一頁最好的狀態是沒有東西。空的時候說的是「都對得上」，不是「沒有資料」。
    empty: '沒有要決定的事。上一次對帳時帳本與磁碟對得上。',
    emptyNeverRun: '沒有要決定的事。這個程序起來之後還沒有對過帳。',
    off: '讀不到待處理清單。Berth 自己的 API 沒有回應，先確認它還活著。',
    detectedAt: '偵測於 {{value}}',
    // 展開區的欄名。路徑是機器字串，走 .value 不走 .label（The Machine String Rule）。
    target: '媒體庫路徑',
    // `orphan_complete` 那一列的路徑在 complete 底下，不在媒體庫裡。
    completePath: 'complete 路徑',
    source: '來源路徑',
    job: '下載',
    // `low_disk_space` 的路徑是量的那個根目錄，不在媒體庫裡。
    measuredPath: '量的目錄',
    library: 'Jellyfin 媒體庫',
    fetchers: 'TVDB fetcher',
    free: '剩下',
    minFree: '門檻',
    // 健康檢查那兩種沒有 Berth 按得了的修法，所以把下一步寫在列上（PRODUCT 原則 4）。
    next: '下一步',
    nextTvdb:
      '到 Jellyfin 的媒體庫設定把 TVDB 的 metadata fetcher 拿掉。Berth 照 TMDB 命名，TVDB 的季集編排可能對不上。拿掉之後下一輪健康檢查（最多 5 分鐘）這一件會自己收掉；是故意掛的就按忽略，之後不會再問。',
    nextDisk: '清出空間，或到服務設定調整門檻。空間回來之後下一輪健康檢查這一件會自己收掉。',
    // 十三種型別各一句（brief §9.1）。
    type: {
      library_link_missing: '媒體庫裡少了這個檔案',
      source_missing: 'complete 裡的來源檔不見了',
      inode_mismatch: '目標與來源不是同一份資料',
      orphan_complete: 'complete 裡有沒人認領的目錄',
      unknown_torrent: 'qBittorrent 上有 Berth 不認得的 torrent',
      unmanaged_library_file: '媒體庫裡有 Berth 不認得的檔案',
      job_without_files: '這一筆入庫完了，帳本卻是空的',
      missing_files: 'qBittorrent 說檔案不見了',
      client_error: 'qBittorrent 報錯',
      client_removed: 'torrent 已經不在 qBittorrent 上',
      jellyfin_item_unresolved: 'Jellyfin 一直沒有收錄這個檔案',
      library_uses_tvdb: '這條 Route 的媒體庫掛著 TVDB',
      low_disk_space: '磁碟剩下的空間低於門檻',
    },
    typeLabel: {
      library_link_missing: '鏈接遺失',
      source_missing: '來源遺失',
      inode_mismatch: 'INODE 不符',
      orphan_complete: '無主目錄',
      unknown_torrent: '無主 TORRENT',
      unmanaged_library_file: '非受管檔案',
      job_without_files: '帳本為空',
      missing_files: '檔案遺失',
      client_error: '客戶端錯誤',
      client_removed: '已被移除',
      jellyfin_item_unresolved: '反查失敗',
      library_uses_tvdb: 'TVDB',
      low_disk_space: '空間不足',
    },
    action: {
      relink: '重新鏈接',
      forget: '承認刪除並清帳本',
      delete_complete: '連 complete 一起刪',
      mark_sourceless: '標記為已無來源',
      replace_with_link: '以硬鏈接取代',
      delete_orphan: '刪除這個目錄',
      replan: '重新規劃',
      relook: '重新反查',
      rescan: '重新掃描媒體庫',
      recheck: '重新校驗',
      accept_loss: '承認遺失',
      retry: '重試',
      resubmit: '重新送單',
      accept_removal: '承認移除',
      // 認領類的三顆（M2 票 10）。前兩顆按下去先選作品。
      adopt: '重新入庫',
      claim_torrent: '認領並建立下載',
      claim_file: '認領進帳本',
      ignore: '忽略',
    },
    working: '處理中…',
    done: '已處理，這一件從清單上收掉了。',
    // 「連 complete 一起刪」的單位是**整筆下載**，不是那一個檔案（brief §9.2）。
    confirmDelete:
      '這會移除這一筆下載的全部：媒體庫裡還在的鏈接、qBittorrent 上的 torrent、complete 底下的檔案，以及它的帳本與紀錄。空出來的空間要等來源與所有鏈接都刪掉才真的回來。',
    confirmDeleteAction: '確認刪除',
    // 另外兩顆會刪東西的（`ACTION_DELETES`），各自說清楚刪的是什麼。
    confirmDeleteOrphan:
      '這會刪掉 complete 底下這一整個目錄與裡面的每一個檔案。qBittorrent 與 Berth 都不認得它；按下去之前會再確認一次它仍然沒有主。',
    confirmReplace:
      '媒體庫裡這一份複製品會被換成來源的硬鏈接。兩份一樣大，但複製品本身會消失——它若是別人改過的版本，就不要按。',
    confirmReplaceAction: '確認取代',
    // 動作失敗時那一列留著 open，就地說出為什麼。
    refusal: {
      issue_missing: '這一件已經不在了。重新整理看看。',
      issue_not_open: '這一件已經被處理過了，多半是另一個分頁先按了。',
      action_not_available:
        '這一顆對這一件按不了：它指不到帳本那一列，或者那一筆下載已經不在、已經不是這一件說的狀態了。',
      source_missing:
        'complete 裡的來源檔也不在了，所以鏈接不回來。要嘛承認刪除並清帳本，要嘛重新下載一次。',
      relink_failed: '鏈接沒有成功。',
      client_unreachable: '問不到 qBittorrent，所以什麼都沒有做。先確認它還活著。',
      reconcile_running: '上一輪對帳還在跑。等它跑完再按。',
      in_use:
        '這個目錄現在有主了（qBittorrent 上有 torrent 指著它，或 Berth 認得它），所以沒有刪。',
      size_differs: '媒體庫那一份與來源現在大小不一樣了，多半被轉碼覆蓋過，所以沒有取代。',
      jellyfin_unreachable:
        '沒有請到 Jellyfin 掃描，這一列也沒有重新排進反查。先到健康頁確認 Jellyfin 還在。',
      delete_failed: '刪除沒有成功。',
      source_unavailable:
        '存下來的下載連結拿不回同一個 torrent（索引站的連結多半過期了），所以沒有送。到作品頁重新搜一次。',
      resubmit_failed: '送了，qBittorrent 不收。修好之後再按一次就是再送一次。',
      route_unusable:
        '這一筆的 Route 現在用不了（被刪了、停用了或紅著），送出去也入不了庫。先到媒體庫路徑設定看那一條。',
      media_required: '先選它是哪一部作品。沒有作品的下載算不出任何一條目標路徑。',
      unclaimable: '配不上帳本，所以什麼都沒有寫。',
    },
    // 媒體庫裡一個檔案配不上帳本的理由（`ClaimMiss`，`rebuild-ledger` 與「認領進帳本」）。
    // 配不上的一律不猜，所以每一句都說得出下一步。
    claimMiss: {
      outside_routes: '它不在任何一條 Route 的目標底下。',
      no_source:
        'complete 裡沒有一個檔案與它是同一份資料：它是一份複製品，或者來源早就刪了。要入庫就重新下載一次。',
      unknown_work: '作品資料夾名說不出是 TMDB 上的哪一部（沒有 [tmdbid-…]，或 TMDB 問不到）。',
      not_berth_naming:
        '它的名字不是 Berth 的命名模板寫得出來的（被改過名，或那一集在 TMDB 上的名字變了）。要它進帳本就從 complete 重新入庫。',
    },
    // `unmanaged_library_file` 那一列：上一次 `rebuild-ledger` 為什麼沒配上。
    unclaimedBecause: '沒配上的理由',
    // 認領時選作品（M2 票 10）：搜 TMDB，選一部，再按一次確認。
    pick: {
      label: '這是哪一部作品',
      placeholder: '輸入作品名搜尋 TMDB',
      searching: '搜尋中…',
      none: '沒有找到。換一個名字試試。',
      off: '搜不到 TMDB。先到健康頁確認 TMDB 的憑證還能用。',
      confirm: '入庫到《{{title}}》',
      cancel: '取消',
      tv: '劇集',
      movie: '電影',
    },
    failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
  },
  review: {
    title: '審核',
    count_one: '{{count}} 件',
    count_other: '{{count}} 件',
    // 超過上限時說出來（plan §6：不分頁，那時候該修的是上游）。
    truncated: '只列出最舊的 {{shown}} 件，共 {{total}} 件。',
    // 這一頁最好的狀態是沒有東西。
    empty: '沒有事在等你。',
    off: '讀不到審核佇列。Berth 自己的 API 沒有回應，先確認它還活著。',
    // 兩段：需要人動手的排前面（`.scratch/m2/review-shape.md`）。Issue 不在這一頁（M3 票 05），
    // 原位一行連到 `/issues`，0 件時不出現。
    section: {
      decide: '要你決定',
      look: '已入庫，等你看一眼',
    },
    issues_one: '另有 {{count}} 件待處理',
    issues_other: '另有 {{count}} 件待處理',
    // plan 那一類（M2 票 07，`.scratch/m2/plan-edit-shape.md`）：一份停在 review 的計劃，逐列可改。
    plan: {
      label: '待審核',
      // 為什麼停下來，**下一步**那一種（PRODUCT 原則 4）。
      reason: {
        low_confidence: '有檔案的季集要你確認',
        medium_not_allowed: '這條 Route 不讓中信心自己入庫，等你點頭',
        nothing_to_import: '這一包沒有東西會進媒體庫，多半送錯了 torrent',
        target_exists: '媒體庫的目標位置上已經有別的檔案',
        audit_undone: '有一個自動入庫的檔案被撤銷了，那一列要重新決定',
      },
      waitingSince: '等候於 {{value}}',
      job: '下載',
      loading: '讀取計劃…',
      off: '讀不到這一份計劃。',
      held_one: '{{count}} 列要你看',
      held_other: '{{count}} 列要你看',
      rest_one: '其餘 {{count}} 個檔案',
      rest_other: '其餘 {{count}} 個檔案',
      // 目標那一行。待審核的列說的是「核准的話」。
      lands: '核准後寫到',
      landed: '已在媒體庫',
      nowhere: '核准後不會寫進媒體庫',
      noProposal: '還沒有季集，先改這一列',
      edit: '改',
      apply: '套用',
      cancel: '取消',
      field: {
        action: '處置',
        season: '季',
        start: '起集',
        end: '迄集',
      },
      endHint: '單集留空',
      applied: '已套用，目標路徑更新了。',
      approve: '核准並入庫',
      reject: '拒絕',
      confirmReject: '丟掉這份計劃（包括逐列改過的），Berth 會重新規劃一次。檔案不動。',
      confirmRejectAction: '確定拒絕',
      working: '處理中…',
      approved: '已核准，開始入庫。',
      rejected: '已拒絕，Berth 重新規劃中。',
      failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
      // 十一種擋下來的理由，各一個下一步。`detail`（檔名或路徑）接在後面。
      refusal: {
        plan_missing: '這份計劃已經不在了，多半是重新規劃把它換掉了。',
        not_pending: '這份計劃已經不在等人了，多半是另一個分頁先核准或拒絕了。',
        item_missing: '這一列已經不在這份計劃裡了。',
        item_applied: '這一列已經在媒體庫裡；要改它得用重新匹配。',
        action_not_allowed: '這個處置與檔案的分類矛盾。',
        episode_required: '入庫的話要填季與起集。',
        episode_range_reversed: '迄集比起集小。',
        episode_not_allowed: '只有入庫的劇集才有季集可填。',
        media_missing: '這份計劃沒有作品資料，算不出寫到哪裡。',
        target_clash: '兩列會寫到同一條路徑，先改其中一列：',
        undecided: '還有列沒有決定，先改成入庫、略過或對不到：',
      },
    },
    // audit 那一列（CONTEXT.md 的 Audit）。
    audit: {
      label: '待確認',
      reason: {
        medium_auto_imported: '信心 medium，已自動入庫',
      },
      // 收起時說出主要原因（M3 票 05，`review/leadReason.ts`）：使用者不必展開就知道要看什麼。
      because: '信心 medium：{{lead}}',
      lead: {
        title_mismatch: '發佈標題看起來不像這部作品',
        strategy_outlier: '這一包其餘的檔案是靠{{strategy}}讀出季集的，這一個不是',
        single_season: '季號是推論的（TMDB 只有一季）',
        season_from_arc: '季號是從篇章名推論的',
        final_season: '季號是推論的（「最終季」當成最後一季）',
        air_date_run: '季號是換算的（依播出日切成幾輪）',
        cour_offset: '集號是換算的（這一季的後半部）',
        absolute_group: '集號是換算的（TMDB 的絕對編號）',
        absolute_cumulative: '集號是換算的（各季集數累加）',
        specials_numbering: '字幕組的特典編號不一定與 TMDB 一致',
      },
      // 同一個 Job 的那一組（M3 票 05）。原因相同就在這裡說一次，組裡的每一列不再重複。
      group: {
        same_one: '{{count}} 個檔案，信心 medium：{{lead}}',
        same_other: '{{count}} 個檔案，信心 medium：{{lead}}',
        none_one: '{{count}} 個檔案信心 medium，已自動入庫',
        none_other: '{{count}} 個檔案信心 medium，已自動入庫',
        mixed_one: '{{count}} 個檔案信心 medium，原因不只一種，展開看每一個',
        mixed_other: '{{count}} 個檔案信心 medium，原因不只一種，展開看每一個',
      },
      confirmAll: '全部確認',
      // 整段的「全部確認」就地確認並說出件數；範圍是畫面上列出的那些。
      confirmSection_one:
        '這一段列出的 {{count}} 個已入庫檔案都會記成「對的」，檔案不動。按下之後才進來的不算在內。',
      confirmSection_other:
        '這一段列出的 {{count}} 個已入庫檔案都會記成「對的」，檔案不動。按下之後才進來的不算在內。',
      confirmSectionAction_one: '確認這 {{count}} 個',
      confirmSectionAction_other: '確認這 {{count}} 個',
      confirmedMany_one: '已確認 {{count}} 個，從佇列上收掉了。',
      confirmedMany_other: '已確認 {{count}} 個，從佇列上收掉了。',
      skipped_one: '{{count}} 個已經在別處確認或撤銷過，跳過了。',
      skipped_other: '{{count}} 個已經在別處確認或撤銷過，跳過了。',
      importedAt: '入庫於 {{value}}',
      target: '媒體庫路徑',
      source: '來源路徑',
      job: '下載',
      reasons: '解析器的理由',
      action: {
        confirm: '確認',
        undo: '撤銷',
      },
      confirmUndo:
        '這會從媒體庫拿掉這一集，Jellyfin 下次掃描就看不到它；complete 裡的檔案不動，這一筆下載回到待審核。',
      confirmUndoAction: '確定撤銷',
      working: '處理中…',
      refusal: {
        ledger_missing: '這一列已經不在了，多半是另一個分頁先撤銷了。',
        not_audited: '這一列已經被確認過了，多半是另一個分頁先按了。',
        unlink_failed: '媒體庫裡那個檔案拿不掉，所以什麼都沒改。',
      },
      failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
      // 動作結果給看不見畫面的人（那一列會直接消失）。
      confirmed: '已確認，這一列從佇列上收掉了。',
      undone: '已撤銷，這一筆下載回到待審核。',
      undoneUnmanaged:
        '已撤銷，這一筆下載回到待審核。媒體庫裡那個檔案已經不是 Berth 放的那一個，所以沒有刪。',
    },
    // unmatched 那一類（brief §7.4、M2 票 08）：對不到、留在 complete 原位的檔案。三個動作打的是
    // `POST /files/rematch`，與 Media 詳情的 Unmatched 區同一支、同一個表單（`RematchForm`）。
    unmatched: {
      label: '對不到',
      reason: {
        left_in_place: '對不到任何一集，留在 complete 原位',
      },
      waitingSince: '規劃於 {{value}}',
      path: '來源路徑',
      job: '下載',
      reasons: '解析器的理由',
    },
    // duplicate 那一類（brief §7.8）：規劃時與媒體庫裡已有的一份重複，自動模式先略過。
    duplicate: {
      label: '重複',
      // 兩種的後果不一樣，句子各說各的（原則 4：說出下一步會怎樣）。
      reason: {
        same_version: '媒體庫已經有同一集、同一組 Tags 的一份',
        span_clash:
          '媒體庫已經有從同一集開始、範圍不同的一份。兩份都留的話，Jellyfin 12 會把它們併成同一集的兩個版本，後面那一集會從集列表消失',
      },
      skippedAt: '略過於 {{value}}',
      path: '新的一份',
      known: '媒體庫裡的',
      job: '下載',
      action: {
        replace: '取代舊版',
        keep_both: '保留兩者',
        skip: '跳過',
      },
      confirmReplace:
        '媒體庫裡舊的那一份會被拿掉，換成這一份；舊版本旁邊的字幕一起拿掉。complete 裡的檔案都不動。',
      confirmReplaceAction: '確定取代',
      confirmKeepClash:
        '兩份都會留在媒體庫：Jellyfin 12 會把它們併成同一集的兩個版本，後面那一集會從集列表消失。',
      confirmKeepClashAction: '仍然保留兩者',
      // 完全相同的那一種：新的檔名會多一個序號標籤（2026-09-23 使用者拍板）。
      keepBothHint:
        '保留兩者時，新的一份檔名會多一個序號標籤（[2]），在 Jellyfin 裡是同一集的另一個版本。',
      working: '處理中…',
      failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
      done: {
        replace: '已取代，媒體庫裡換成新的一份了。',
        keep_both: '兩份都留在媒體庫了。',
        skip: '已跳過，這一份留在 complete 原位。',
      },
    },
  },
  // 修正一個檔案（brief §9.4、M2 票 08）：`/review` 的對不到那一列與 Media 詳情共用同一個表單。
  rematch: {
    fix: '修正',
    field: {
      action: '改成',
      season: '季',
      start: '起集',
      end: '迄集',
    },
    endHint: '單集留空',
    action: {
      import: '指派到某一集',
      importMovie: '入庫',
      extra: '標記為特典',
      skip: '忽略',
    },
    apply: '套用',
    cancel: '取消',
    working: '處理中…',
    // 已入庫的檔案：改完它就不在原本那條路徑了（原則 2：破壞性動作說清楚）。
    confirmMove:
      '媒體庫裡現在這一條會被拿掉、換到新的位置；旁邊的字幕跟著走。complete 裡的檔案不動。',
    confirmExtra:
      '它會搬到特典資料夾；特典旁邊不掛字幕，旁邊的字幕一起拿掉。complete 裡的檔案不動。',
    confirmDrop: '這會從媒體庫拿掉它，旁邊的字幕一起拿掉。complete 裡的檔案不動。',
    confirmAction: '確定修正',
    done: '已修正。',
    failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
    // 十四種擋下來的理由，各一個下一步。`detail`（檔名、路徑或系統原文）接在後面。
    refusal: {
      ledger_missing: '這個檔案的帳本已經不在了，多半是另一個分頁先改了。',
      file_missing: '這個檔案已經不在這筆下載裡了。',
      not_unmatched: '這個檔案已經不是「對不到」了，多半是另一個分頁先決定了。',
      plan_pending: '這筆下載的計劃還在等審核，先到審核佇列改那一列。',
      not_duplicate: '這一列已經不在等人了，多半是另一個分頁先決定了。',
      action_not_allowed: '這個處置與檔案的分類矛盾。',
      episode_required: '指派到某一集要填季與起集。',
      episode_range_reversed: '迄集比起集小。',
      episode_not_allowed: '只有指派到某一集才有季集可填。',
      media_missing: '這個檔案沒有作品資料，算不出寫到哪裡。',
      route_missing: '收這部作品的 Route 不在了。',
      target_taken: '目標位置上已經有別的檔案，Berth 不覆寫它：',
      link_failed: '鏈接建不起來，所以什麼都沒改：',
      unlink_failed: '媒體庫裡舊的那一條拿不掉，所以什麼都沒改：',
    },
  },
  reconcile: {
    start: '立刻對帳',
    running: '對帳中…',
    // 跑完之後那一行摘要。
    lastRun: '上一輪 {{time}}',
    opened_one: '開了 {{count}} 件',
    opened_other: '開了 {{count}} 件',
    updated_one: '更新 {{count}} 件',
    updated_other: '更新 {{count}} 件',
    neverRun: '這個程序起來之後還沒有對過帳。',
    // 各方一列：「比到哪、幾筆」（plan §3.2）。Jellyfin 那一方是票 09 加的：它只把反查過的
    // item 換新，不開 Issue。
    sides: '對帳進度',
    side: {
      ledger: '帳本',
      client: 'qBittorrent',
      complete: 'COMPLETE',
      library: '媒體庫',
      jellyfin: 'Jellyfin',
    },
    counted_one: '比了 {{count}} 筆',
    counted_other: '比了 {{count}} 筆',
    // **問不到不是「不見了」**（brief §16.2）：那一方跳過並說出原因。
    unavailable: '問不到',
    skipped: '跳過了 {{value}}',
    failed: '對帳沒有開始。Berth 自己的 API 沒有回應，先確認它還活著。',
  },
  jobs: {
    title: '下載',
    count_one: '{{count}} 筆',
    count_other: '{{count}} 筆',
    empty: '還沒有送過任何下載。到探索頁找一部作品，在它的頁面上搜 torrent 再送單。',
    toDiscover: '回探索頁',
    off: '讀不到下載列表。Berth 自己的 API 沒有回應，先確認它還活著。',
    media: '作品',
    hash: 'info hash',
    // 這一列沒有欄頭，所以每一格自己帶標籤。大小與進度都要等票 10 的客戶端輪詢才有值。
    sizeInline: '大小 {{value}}',
    progressInline: '進度 {{value}}',
    retry: '重新送單',
    retrying: '送單中…',
    // 不叫「重新入庫」：那是 CONTEXT.md 的 Reimport（M2，以 complete 下的目錄為來源）。
    retryImport: '再試一次入庫',
    retryingImport: '入庫中…',
    retried: '已重試，現在是{{state}}。',
    retryOff: '重試沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
    // CONTEXT.md 的 Reimport：以 complete 裡那一包重新入庫，不必 torrent 還在（brief §9.3）。
    reimport: '重新入庫',
    reimporting: '重新入庫中…',
    reimportOff: '重新入庫沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
    reimported: '已排進重新入庫，現在是{{state}}。',
    // 停在待審核的那一列：`user` 按不了審核，只能等（brief §11）。
    waitingForAdmin: '等管理員審核',
    // admin 在停在 review 的那一列看到的是去處理它的路，不是「等」（M2 票 07）。
    toReview: '到審核佇列處理',
    // Job 詳情頁 `/jobs/:hash`（M2 票 12、`.scratch/m2/job-detail-shape.md`）。
    detail: {
      open: '下載詳情',
      back: '回下載列表',
      sentBy: '送單的人',
      nobody: '沒有人在場',
      error: '服務回的原文',
      files: '檔案與決策',
      noPlan: '還沒有計劃：拿到檔案清單之後 Berth 才算得出一份。',
      history: '計劃歷史',
      historyEmpty: '這份計劃還沒有任何紀錄。',
      timeline: '時間線',
      loading: '讀取這筆下載…',
      missing: '找不到這筆下載',
      missingHint: '網址可能打錯了，或它已經被刪除並清除了紀錄。',
      off: '讀不到這筆下載。Berth 自己的 API 沒有回應，先確認它還活著。',
    },
    // 十六個狀態一次定義完（`domain.JobState`）：M1 票 09 只走得到前三個，
    // 其餘由票 10 起的迴圈驅動，而它們是同一個封閉集合。
    state: {
      requested: '已建立',
      submitted: '已送出',
      submit_failed: '送單失敗',
      metadata_ready: '已取得檔案清單',
      downloading: '下載中',
      stalled: '停滯',
      missing_files: '檔案不見了',
      client_error: '客戶端錯誤',
      client_removed: '已從客戶端移除',
      completed: '下載完成',
      planning: '規劃中',
      review: '待審核',
      importing: '入庫中',
      imported: '已入庫',
      import_failed: '入庫失敗',
      removed: '已刪除',
    },
    trigger: {
      manual: '手動',
      rss: 'RSS',
      reimport: '重新入庫',
    },
    event: {
      created: '已建立',
      submitted: '已送出',
      submit_failed: '送單失敗',
      retried: '重試',
      metadata_received: '檔案清單',
      progress: '進度',
      stalled: '停住',
      completed: '下載完成',
      issue_detected: '需要處理',
      preplan: '預估計劃',
      plan_generated: '計劃',
      review_required: '待審核',
      review_decided: '已審核',
      linked: '已鏈接',
      link_failed: '鏈接失敗',
      jellyfin_scan_requested: '已通知 Jellyfin',
      jellyfin_item_resolved: 'Jellyfin 已收錄',
      jellyfin_request_failed: 'Jellyfin 請求沒成',
      deleted: '已刪除',
      audit_confirmed: '已確認',
      audit_undone: '已撤銷入庫',
      rematched: '已修正',
      duplicate_skipped: '略過重複',
      duplicate_decided: '重複已決定',
      recovered: '已接回',
      round_failed: '處理時出錯',
    },
    timeline: {
      loading: '讀取時間線…',
      empty: '這一筆還沒有任何事件。',
      off: '讀不到時間線。',
      // `/jobs` 展開區的摘要只畫最近三段（M2 票 12）。
      earlier_one: '較早的 {{count}} 筆事件在詳情頁。',
      earlier_other: '較早的 {{count}} 筆事件在詳情頁。',
      retried: '狀態退回「已建立」，接著再送一次。',
      retriedImport: '狀態退回「入庫中」，從還沒鏈接的檔案接著做。',
      // 待處理上那幾顆（M2 票 09、09c）。`action` 是後端寫的，不是前端猜的。
      retriedRecheck: '請 qBittorrent 重新校驗並接著下載。',
      retriedRestart: '請 qBittorrent 重新開始這一筆。',
      retriedReplan: '狀態退回「下載完成」，重新規劃一次。',
      // 重新入庫（M2 票 10）：以 complete 裡那一包為來源，照現在的檔案重新規劃與入庫。
      retriedReimport: '重新入庫：照 complete 裡現在的檔案重新規劃一次。',
      linkedFiles_one: '{{count}} 個檔案',
      linkedFiles_other: '{{count}} 個檔案',
      linkedTargets: '列出目標路徑',
      scanRequested_one: '通知了 {{count}} 個檔案的路徑',
      scanRequested_other: '通知了 {{count}} 個檔案的路徑',
      resolved_one: '{{count}} 個檔案在 Jellyfin 裡找到了',
      resolved_other: '{{count}} 個檔案在 Jellyfin 裡找到了',
      // 不擋入庫的失敗，說下一步會怎樣（理由翻譯，原文接在後面）。
      jellyfin: {
        scan: '通知沒送到。Jellyfin 自己的排程掃描會補上。',
      },
      files_one: '{{count}} 個檔案 · {{size}}',
      files_other: '{{count}} 個檔案 · {{size}}',
      resumed: '又動起來了',
      idle_one: '{{count}} 分鐘沒有動靜',
      idle_other: '{{count}} 分鐘沒有動靜',
      // 停下來的理由，**短的那一種**：時間線說的是當時為什麼停，該怎麼辦在計劃那一塊。
      review: {
        low_confidence: '有檔案的季集推不出來',
        medium_not_allowed: '這條 Route 不自動入庫 medium',
        nothing_to_import: '沒有東西會進媒體庫',
        target_exists: '目標位置上已經有別的檔案',
        audit_undone: '有一個自動入庫的檔案被撤銷了',
      },
      // 核准與拒絕（M2 票 07）。拒絕之後規劃器整份重算，所以下一筆就是新的那一份。
      reviewApproved_one: '管理員核准了，{{count}} 個檔案要入庫',
      reviewApproved_other: '管理員核准了，{{count}} 個檔案要入庫',
      reviewRejected: '管理員拒絕了這份計劃，Berth 重新規劃',
      // audit 的兩顆（M2 票 06）。目標路徑是機器字串，接在後面。
      auditConfirmed: '管理員看過這個 medium 自動入庫的檔案，說它是對的',
      auditUndone: '管理員撤銷了這個檔案的入庫，這一筆回到待審核',
      auditUndoneGone:
        '管理員撤銷了這個檔案的入庫（它在那之前已經不在媒體庫裡了），這一筆回到待審核',
      // 那條路徑上的已經不是 Berth 放的那一個（M3 票 01、CONTEXT.md 的 Unmanaged）：Berth 沒有刪它。
      auditUndoneUnmanaged:
        '管理員撤銷了這個檔案的入庫，這一筆回到待審核。媒體庫裡那個檔案已經不是 Berth 放的那一個，所以沒有刪',
      keptUnmanaged_one: '{{count}} 個媒體庫檔案已經不是 Berth 放的那一個，沒有刪：',
      keptUnmanaged_other: '{{count}} 個媒體庫檔案已經不是 Berth 放的那一個，沒有刪：',
      // rematch 與重複版本（M2 票 08）。「從什麼改成什麼」由處置與季集組成，路徑是機器字串，另起一行。
      rematched: '管理員改了這個檔案：{{from}} → {{to}}',
      notInLibrary: '不在媒體庫',
      duplicateSkipped_one: '{{count}} 個檔案與媒體庫裡已有的一份重複，先略過，等你在審核佇列決定',
      duplicateSkipped_other:
        '{{count}} 個檔案與媒體庫裡已有的一份重複，先略過，等你在審核佇列決定',
      duplicateDecided: {
        replace: '管理員用這一份取代了媒體庫裡的舊版本',
        keep_both: '管理員讓兩個版本都留在媒體庫',
        skip: '管理員決定不要這一份重複的檔案，它留在 complete 原位',
      },
      // 刪除範圍那一筆（M2 票 04）。說的是**真的**做掉了什麼，不是勾了哪幾個。
      deletedLinks_one: '移除 {{count}} 個鏈接',
      deletedLinks_other: '移除 {{count}} 個鏈接',
      deletedSources_one: '刪掉 {{count}} 個下載檔案',
      deletedSources_other: '刪掉 {{count}} 個下載檔案',
      deletedTorrent: '從 qBittorrent 移除',
      deletedPurged: '清除紀錄',
      freed: '空出 {{size}}',
      // 硬鏈接的另一半還在時一個位元組都沒回到磁碟。時間線照實說，不說「已釋放 0 B」。
      freedNothing: '沒有空出空間：還有別的名字指著同一份資料。',
      // poller 自己接回主幹的那一筆（M3 票 02）：說是哪一邊好了。
      recovered: {
        submit_failed: 'qBittorrent 其實收下了這一筆，接著下載。',
        missing_files: 'qBittorrent 裡的檔案回來了，接著下載。',
        client_error: 'qBittorrent 的錯誤解除了，接著下載。',
        client_removed: '這一筆又回到 qBittorrent 裡了，接著下載。',
      },
      roundFailed: 'Berth 處理這一筆時出錯，下一輪會再試：',
      // 理由翻譯，原文不翻譯：後面接的 `client_state` 是 qBittorrent 的機器字串。
      issue: {
        missing_files: 'qBittorrent 說檔案不見了。到它的介面上重新檢查那一筆。',
        client_error: 'qBittorrent 自己報錯。看它的介面或 log 才知道是哪一種。',
        client_removed: 'torrent 從 qBittorrent 上消失了。下載好的檔案可能還在原位。',
        unknown_torrent:
          '這個 torrent 出現在 qBittorrent 上時，Berth 還沒有對應的下載紀錄。多半是有人直接在那邊加的，或這裡的資料庫被還原過。',
        jellyfin_item_unresolved:
          'Jellyfin 一直沒有列出這幾個入庫的檔案。多半是它看不到這條路徑，或把資料夾認成了別的作品——到 Jellyfin 的媒體庫裡找找看。',
      },
    },
    // 匯入計劃：逐檔的決定、信心與理由（brief §6.5、票 11）。M1 唯讀——逐列編輯與核准
    // 是 M2 的 Review Queue。
    plan: {
      title: '匯入計劃',
      loading: '讀取計劃…',
      off: '讀不到這一份計劃。',
      planned_one: '{{count}} 個檔案要入庫',
      planned_other: '{{count}} 個檔案要入庫',
      // 抬頭與每一組講同一套信心的詞（票 03 第 10 條）：這裡是「高 / 中 / 低」，
      // 組的摘要是「高信心 / 中信心 / 低信心」，不再把原始列舉值印在中文句子裡。
      // 一組的檔案數（M1.5 票 09：依處置 × 季 × 信心分組）。
      files_one: '{{count}} 個檔案',
      files_other: '{{count}} 個檔案',
      levels: '信心 高 {{high}} / 中 {{medium}} / 低 {{low}}',
      estimate: '這是下載中的預估，沒有讀過檔案本身；下載完成之後會重算一份。',
      status: {
        preplan: '預估',
        auto: '自動入庫',
        pending_review: '待審核',
        approved: '已核准',
        rejected: '已拒絕',
        applied: '已套用',
        failed: '失敗',
      },
      // 三種理由、三種下一步（PRODUCT 原則 4）。M1 沒有審核 UI，所以這裡要說得出
      // 使用者現在真的做得到的那一步。
      reason: {
        low_confidence:
          '有檔案的季集推不出來，或這一包的數量與 TMDB 對不上。管理員在審核佇列逐列確認季集之後核准；TMDB 剛補上季集的話也可以按「重新規劃」。',
        medium_not_allowed:
          '這條 Route 不讓中信心的檔案自己入庫，所以整份計劃停下來等人看。管理員在審核佇列看過每一列之後核准就會入庫。',
        nothing_to_import: '這一包裡沒有任何一個檔案會進媒體庫。多半是送錯了 torrent。',
        target_exists:
          '媒體庫裡這個位置已經有一個不是 Berth 鏈接的檔案，Berth 不會覆寫它；其餘檔案已經入庫了。把那個檔案移走，或在審核佇列把那一列改成略過，再核准。',
        audit_undone:
          '管理員從審核佇列撤銷了一個 medium 自動入庫的檔案：那個檔案已經不在媒體庫裡，complete 裡的來源還在。這份計劃回來等人決定那一列該是哪一集。',
      },
      action: {
        import: '入庫',
        extra: '特典',
        subtitle: '字幕',
        skip: '略過',
        unmatched: '對不到',
        review: '待審核',
      },
      confidence: {
        high: '高信心',
        medium: '中信心',
        low: '低信心',
      },
      // 逐檔那一列的標籤。目標路徑相對 Route 的媒體庫目錄。
      target: '目標',
      audit: '已入庫待確認',
      // 逐檔的理由（`domain.ReasonCode`，M2 票 07）：code 加參數，句子在這裡。參數是檔名、
      // 季集、日期這種不翻譯的事實；`kind`、`action`、`strategy` 先翻好再帶進來（`plans/reasonText.ts`）。
      why: {
        movie: '這是一部電影，沒有季集',
        media_by_title: '下載沒有帶作品，以標題認出是 {{title}}',
        title_exact: '發佈標題與 {{title}} 完全相同',
        title_contained: '發佈名裡有整串 {{title}}',
        title_partial: '發佈名帶著 {{title}} 的大部分詞',
        year_matches: '年份 {{year}} 對得上',
        year_differs: '發佈寫的是 {{year}}，這部作品是 {{expected}}',
        title_mismatch: '發佈標題 {{release_title}} 看起來不像 {{title}}',
        no_media: '下載沒有帶作品，沒有季集可以對照',
        season_from_job: '下載指定了第 {{season}} 季',
        season_from_release: '發佈名寫了第 {{season}} 季',
        season_from_folder: '資料夾寫了第 {{season}} 季',
        season_from_arc: '發佈名帶著篇章名 {{arc}}，那是第 {{season}} 季',
        final_season: '發佈名說最終季，最後一季是第 {{season}} 季',
        single_season: '只有集號，而 TMDB 上這部作品只有一季',
        absolute_group: 'TMDB 的絕對編號把 #{{number}} 放在 {{episode}}',
        absolute_cumulative: '各季集數依序累加，#{{number}} 落在 {{episode}}',
        cour_offset:
          '第 {{season}} 季的第 {{part}} 部分從第 {{first}} 集開始，所以它的第 {{number}} 集是 {{episode}}',
        air_date_run:
          'TMDB 沒有第 {{season}} 季；依播出日切成 {{runs}} 輪，第 {{season}} 輪從 {{episode}} 開始',
        episode_not_on_tmdb: 'TMDB 第 {{season}} 季沒有第 {{number}} 集',
        absolute_within_first_season:
          '#{{number}} 沒有超過第 {{season}} 季的 {{episodes}} 集，也可能是後面某季重新從 01 數的第 {{number}} 集',
        air_date_unknown: '發佈說它在 {{aired}} 播出，但 TMDB 沒有 {{episode}} 的播出日',
        air_date_mismatch: '發佈說它在 {{aired}} 播出，TMDB 說 {{episode}} 在 {{tmdb_aired}}',
        range_spans_seasons: '發佈涵蓋 {{start}}–{{end}}，但那一段放不進同一季',
        specials_numbering: '字幕組的特典編號與 TMDB 的 S00 不一定一致',
        classified: '分類是{{kind}}，不需要人看',
        disc_structure: '光碟結構，Berth 不拆',
        own_numbered_special: '字幕組自己編號的特典，TMDB 的特典編號不同',
        no_episode: '推不出季集',
        subtitle_orphan: '這一包裡沒有影片配得上這個字幕',
        subtitle_same_name: '字幕與影片同名',
        subtitle_folder_episode: '字幕在字幕資料夾裡，寫著第 {{number}} 集',
        subtitle_follows: '跟著 {{video}}',
        video_not_imported: '它的影片是「{{action}}」，字幕跟著走',
        target_contested: '這一包裡另一個檔案也會寫到 {{target}}',
        span_clash:
          '同一包裡另一個正片從同一集開始、範圍不同；Jellyfin 12 只看季與集，會把它們併成一集，後面那幾集會從集列表上消失',
        library_span_clash:
          '媒體庫已經有 {{known}}，從同一集開始、範圍不同；Jellyfin 12 會把它們併成一集，後面那幾集會從集列表上消失',
        too_many_files:
          '這一包把 {{files}} 個檔案對進第 {{season}} 季，TMDB 說那一季只有 {{episodes}} 集',
        strategy_outlier: '這一包其餘的檔案是靠{{strategy}}讀出來的，這一個不是',
        season_complete: '這一包從頭到尾蓋滿第 {{season}} 季',
        medium_held_by_route: '這條 Route 不讓中信心的檔案自己入庫',
        set_by_user: '管理員改過這一列',
        same_version: '媒體庫已經有 {{known}}：同一集、同一組 Tags',
      },
      // 理由裡的 `strategy`（`domain.MappingStrategy`）：季集是靠什麼讀出來的。
      strategy: {
        explicit: '檔名明寫',
        folder: '資料夾',
        context: '下載指定',
        arc_name: '篇章名',
        single_season: '單季',
        absolute_group: 'TMDB 絕對編號',
        absolute_cumulative: '累計集數',
        air_date_offset: '播出日',
        cour_offset: '分部',
        movie: '電影',
      },
      // 檔案分類（`domain.FileKind`，brief §6.2）。
      kind: {
        video: '影片',
        subtitle: '字幕',
        font: '字型',
        audio: '音訊',
        image: '圖片',
        archive: '壓縮檔',
        sample: '樣片',
        disc: '光碟結構',
        extra: '特典',
        other: '其他',
      },
      replan: '重新規劃',
      replanning: '規劃中…',
      replanOff: '重新規劃沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
      replanned: '已重新規劃，現在是{{state}}。',
    },
    // 八種被擋下來的理由，八種下一步（PRODUCT 原則 4）。
    refusal: {
      media_missing: 'Berth 手上沒有這部作品。回到它的詳情頁重新開一次。',
      route_missing: '那條 Route 不在了。重新選一條。',
      route_kind_mismatch:
        '那條 Route 收不下這種作品——劇集只進得了 tvshows 媒體庫，電影只進得了 movies。',
      route_disabled: '那條 Route 停用了。到設定裡把它打開，或改選另一條。',
      route_unhealthy: '那條 Route 現在是紅的，送出去也一定進不了庫。到健康頁看是哪一條纜繩斷了。',
      source_unavailable: '索引站給不出這一份 torrent。可能是連結過期了——重新搜一次再送。',
      job_missing: '這一筆下載不在了。',
      not_retryable:
        '這一筆現在不能重試——只有送單失敗或入庫失敗的那些可以。重新整理看看它現在的狀態。',
      not_replannable:
        '這一筆現在不能重新規劃——已經在入庫的那一份計劃正被照著動檔案。重新整理看看它現在的狀態。',
      client_unreachable: '連不上 qBittorrent，所以什麼都沒有刪。先確認它還活著，再按一次。',
      delete_files_requires_remove_torrent:
        '要刪下載目錄裡的檔案，得同時從 qBittorrent 移除這個 torrent——否則它會在下一次重新檢查時把整包再抓一遍。',
      not_reimportable:
        '這一筆現在不能重新入庫——它還在下載、規劃或入庫中，或者它從來沒有下載完（complete 裡只有殘件）。重新整理看看它現在的狀態。',
      content_missing:
        'complete 裡已經沒有這一包了（或裡面一個檔案都沒有），所以什麼都沒有動。要入庫就重新下載一次。',
      moved_on:
        '你按下去之後，這一筆已經被別處改過了（可能是另一個分頁剛刪掉它），所以什麼都沒有動。重新整理看看它現在的狀態。',
      low_disk_space:
        '下載目錄的磁碟空間低於門檻，所以沒有送出去。空出空間，或在服務設定裡調低門檻，再送一次。',
      job_removed:
        '這個 torrent 之前下載過、後來刪除了，那一筆紀錄還在，所以不會再下載一次。到那一筆決定：complete 裡還有檔案就重新入庫，要重新下載就先連紀錄一起刪掉（兩者都要管理員）。',
      review_needs_admin:
        '這一筆停在審核，重新規劃會丟掉管理員審過的那一份，所以只有管理員按得了。',
    },
    // 刪除範圍（brief §9.2、M2 票 04）。四個旗標各自說出後果，預設全不勾。
    delete: {
      label: '刪除',
      pending: '刪除中…',
      confirm: '確認刪除',
      title: '要刪掉哪幾樣',
      // 一句把「以什麼為單位」說清楚：刪的是這一筆下載，不是這部作品。
      lede: '刪的是這一筆下載經手的東西。同一部作品的其他下載不受影響。',
      unlink: '移除媒體庫裡的硬鏈接',
      unlinkHint: 'Jellyfin 下次掃描時會少掉這幾個檔案。下載目錄裡的原檔不動。',
      removeTorrent: '從 qBittorrent 移除這個 torrent',
      removeTorrentHint: '不刪檔案，但做種會停。',
      deleteFiles: '刪除下載目錄裡的檔案',
      deleteFilesHint: '要同時移除 torrent，否則 qBittorrent 會把整包再抓一遍。',
      // 沒勾「移除 torrent」時它是鎖住的，而鎖住的控制項要說得出為什麼（PRODUCT 原則 4）。
      deleteFilesLocked: '先勾上面那一格才選得了。',
      purge: '清除帳本與這一筆的紀錄',
      purgeHint: '不勾的話它留在清單上，狀態是「已刪除」，時間線也還在。',
      // 估算（brief §9.2）。逐一 stat，所以它慢——畫面要說得出自己正在做什麼。
      estimate: {
        // 「正在算」不是轉圈圈：它說得出正在量什麼、為什麼要等。
        pending: '正在逐一量測這幾個檔案…',
        off: '算不出可以空出多少。Berth 自己的 API 沒有回應——刪除仍然按得下去。',
        links_one: '媒體庫 {{count}} 個鏈接',
        links_other: '媒體庫 {{count}} 個鏈接',
        sources_one: '下載目錄 {{count}} 個檔案',
        sources_other: '下載目錄 {{count}} 個檔案',
        missing_one: '另有 {{count}} 個帳本上有、磁碟上已經不在了',
        missing_other: '另有 {{count}} 個帳本上有、磁碟上已經不在了',
        frees: '這樣刪會空出 {{size}}。',
        // 硬鏈接的規矩：來源與所有鏈接都刪掉，那些位元組才回到磁碟（brief §9.2）。
        freesNothing:
          '這樣刪不會空出空間：媒體庫的鏈接與下載目錄的檔案是同一份資料，要兩邊都刪掉才算數。',
        held: '其中 {{size}} 有 Berth 不知道的鏈接握著，怎麼刪都拿不回來。',
      },
      done: '已移除 {{links}} 個鏈接、刪掉 {{sources}} 個檔案，空出 {{size}}。',
      doneNothing: '已移除 {{links}} 個鏈接、刪掉 {{sources}} 個檔案，沒有空出空間。',
      // 時間線上那一筆列得出是哪幾個；這裡只說有幾個（M3 票 01）。
      kept_one: '{{count}} 個媒體庫檔案已經不是 Berth 放的那一個，沒有刪。',
      kept_other: '{{count}} 個媒體庫檔案已經不是 Berth 放的那一個，沒有刪。',
      off: '刪除沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
    },
  },
  // 送單（票 09）。資料夾名在這裡定下來，所以按下去之前它要出現在畫面上。
  submit: {
    start: '送單',
    submit: '確認送單',
    submitting: '送單中…',
    confirm: '送出去之後，這部作品在媒體庫裡的資料夾會是：',
    needRoute: '先在上面選一條「入庫到」的 Route。這一串字會是它在媒體庫裡的資料夾名：',
    needRouteError: '先在上面選一條「入庫到」的 Route。',
    destination: '入庫到「{{route}}」',
    willFreeze: '送單成功那一刻這串字就定下來，之後 TMDB 改標題也不會動它。',
    alreadyFrozen: '這串字已經定下來了，這一次不會再動它。',
    done: '已送出',
    already: '這一個已經在了',
    toJobs: '看下載列表',
    toRemovedJob: '看那一筆下載',
    off: '送單沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
  },
  // 向 TMDB 要東西沒要到的四種樣子。探索頁與 Media 詳情頁共用同一塊 `TmdbNotice`，
  // 所以文案也在同一個地方——各寫一份的話兩頁遲早會對同一件事說不同的下一步。
  tmdb: {
    problem: {
      credential_missing:
        'Berth 還沒有 TMDB 憑證。它不內建任何一把，要你自己去 themoviedb.org 申請並填進設定精靈。',
      credential_rejected: 'TMDB 不接受這把憑證。它可能被撤銷了，或貼進來時少了幾個字。',
      unreachable: '連不上 TMDB。可能是這台機器沒有對外網路，或 TMDB 正在維護。',
      not_found: 'TMDB 上沒有這部作品。它可能已經被合併或刪除了——回探索頁重新找一次。',
      toSetup: '前往設定精靈',
      askAdmin: '請管理員到設定精靈補上 TMDB 憑證。',
      retry: '重試',
    },
  },
  health: {
    title: '健康',
    deniedChip: '沒有權限',
    denied: '設定只有管理員改得了，所以你被送到這一頁。健康頁是唯讀的診斷，每個人都看得到。',
    checking: '檢查中…',
    unreachable: '連不上 Berth 後端。確認程序是否還在執行。',
    interval: '每 {{minutes}} 分鐘自動檢查一次',
    lastChecked: '上次檢查',
    lastOk: '最後成功',
    never: '沒有紀錄',
    recheck: '立即重測',
    rechecking: '重測中…',
    recheckFailed: '重測沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    failures_one: '連續失敗 {{count}} 次',
    failures_other: '連續失敗 {{count}} 次',
    state: {
      ok: '已繫上',
      drift: '設定被改過',
      failed: '阻擋',
      unknown: '尚未檢查',
      unconfigured: '尚未接上',
    },
    poller: {
      title: '下載迴圈',
      lastRound: '上次輪詢',
      every: '有下載時每 {{seconds}} 秒',
      failures: '連續失敗',
      error: '最後的錯誤',
      unknown: {
        title: '無主 torrent',
        count_one: '{{count}} 筆',
        count_other: '{{count}} 筆',
        help: 'qBittorrent 上掛著 Berth 記號、而 Berth 沒有對應下載紀錄的 torrent。多半是有人直接在 qBittorrent 那邊加的，或這裡的資料庫被還原過。Berth 不會動它們。',
      },
    },
    routes: {
      title: '媒體庫路徑',
      count_one: '{{count}} 條 Route',
      count_other: '{{count}} 條 Route',
      expand: '展開檢查',
      collapse: '收起',
      empty: '還沒有 Route。在設定精靈的最後一個泊位建立它們，Berth 才有地方寫入。',
    },
    fix: {
      title: '修正',
      banned:
        'qBittorrent 因為連續登入失敗把 Berth 這台的 IP 封了。**改帳密沒有用**——那只會再失敗幾次，把封鎖時間重新算一輪。等封鎖過期（qBittorrent 預設 1 小時），或到它的介面上把封鎖清掉；重啟 qBittorrent 容器也會清掉，因為封鎖只存在記憶體裡。確定帳密沒問題之後 Berth 下一輪就會自己變綠。',
      bundled:
        '這個服務是這套 compose 起的，所以先確認那個容器還在跑。三條指令的順序就是排查順序：還在嗎、把它起來、它自己說了什麼。',
      existing:
        '這是你自己的服務，Berth 只知道它現在回不出東西。位址或憑證變了的話回設定精靈重新填一次。',
      unconfigured: '這個服務還沒接上。到設定精靈接它——沒接上的話它負責的那件事一律不會發生。',
      unsupported:
        'Berth 需要 Jellyfin 12.0 以上（12.0 就是原本的 10.12）。升級前先把 Jellyfin 的 /config 完整備份 —— 12 改了資料庫，降不回去；再移除第三方插件，10.11 的插件在 12 載入不了。升級後完整掃描一次媒體庫。',
      drift:
        'Berth 的建議設定被改掉了（{{keys}}）。服務本身還在動，但下載路徑或自動管理一旦不對，入庫遲早會失敗。',
    },
    toSetup: '到設定精靈',
    toSettings: '到服務設定',
  },
  settings: {
    title: '服務設定',
    lede: '位址與憑證在設定精靈改。這一頁做四件事：重測連線、Jellyfin 的對外網址、磁碟空間門檻，以及把被改掉的建議設定還原。',
    test: '測試連線',
    testing: '測試中…',
    testFailed: '測試沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    editHint: '改位址或憑證',
    tabs: {
      label: '設定',
      services: '服務',
      routes: '媒體庫路徑',
    },
    // 深連結的主機（票 13）。它不是連線資訊，所以住在這裡而不是精靈。
    jellyfin: {
      title: 'Jellyfin 對外網址',
      lede: '媒體庫「在 Jellyfin 開啟」用的網址，不是 Berth 自己連過去的那一條。Jellyfin 在反向代理後面、或在另一個網域時才需要填。',
      // 不與區塊標題同字：區塊以 `aria-labelledby` 指向標題，同字會讓兩個東西叫同一個名字。
      label: '對外網址',
      placeholder: 'https://jellyfin.example.com',
      derivedHost: '現在沒有填：深連結開在這個瀏覽器目前的主機名，port {{port}}。',
      derivedUrl: '現在沒有填：深連結開在 {{url}}。',
      set: '深連結開在 {{url}}。',
      unknown: '現在沒有填，而 Berth 也推不出 Jellyfin 開在哪裡——填一個吧。',
      save: '儲存',
      saving: '儲存中…',
      saved: '已儲存。',
      invalid: '要是一個 http:// 或 https:// 開頭的網址。',
      failed: '沒有存進去。Berth 自己的 API 沒有回應，先確認它還活著。',
    },
    // 磁碟空間門檻（M2 票 09c）。形狀照 Sonarr 的 Minimum Free Space，單位不同。
    disk: {
      title: '磁碟空間門檻',
      lede: 'incomplete 或 complete 所在的磁碟剩下的空間低於這個值，就在待處理開一件；空間回來之後它自己收掉。Berth 以硬鏈接入庫不佔空間，吃空間的是下載，所以單位是 GB。',
      label: '最少剩下（GB）',
      hint: '0 是不量。',
      // 與上面那一區的「儲存」不同字：同一頁兩顆同名的按鈕，螢幕閱讀器分不出是哪一顆。
      save: '儲存門檻',
      saving: '儲存中…',
      saved: '已儲存，並且立刻重量了一次。',
      invalid: '要是 0 或更大的整數。',
      failed: '沒有存進去。Berth 自己的 API 沒有回應，先確認它還活著。',
    },
    drift: {
      title: 'qBittorrent 建議設定',
      clean: '五個建議鍵都還是建議值。',
      changed_one: '{{count}} 個鍵與建議值不同。',
      changed_other: '{{count}} 個鍵與建議值不同。',
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
  // Route 設定頁（票 14）。「Route」保留原文：它是 CONTEXT.md 的名詞，精靈與健康頁也這樣寫。
  routeSettings: {
    title: '媒體庫路徑',
    lede: '每條 Route 是一個 Jellyfin 媒體庫加上一條寫入目標；同一個媒體庫可以有好幾條，例如兩顆碟各一條。停用的 Route 不收新的送單；還有下載或入庫檔案指著它時，它刪不得。',
    empty: '還沒有 Route。在設定精靈的最後一個泊位建立它們，Berth 才有地方寫入。',
    disabled: '停用',
    manage: '管理',
    collapse: '收起',
    link: '到 Route 設定',
    usage: {
      jobs_one: '{{count}} 筆下載',
      jobs_other: '{{count}} 筆下載',
      files_one: '{{count}} 個入庫檔案',
      files_other: '{{count}} 個入庫檔案',
    },
    edit: {
      name: '名稱',
      enabled: '啟用',
      enabledHint:
        '停用的 Route 不收新的送單，已經在路上的下載照常入庫。啟用時會先把五條纜繩重跑一次。',
      identity:
        'slug 與寫入目標建立之後就不能改：分類、complete 子目錄與帳本都認它們。要換目標就新增一條、刪掉這一條。',
      save: '儲存',
      saveRechecks:
        '儲存會重跑下面那五條纜繩：那一輪會建 qBittorrent 分類，並在寫入目標寫一個探測檔。',
      saving: '儲存並檢查中…',
      saved: '已儲存。',
      unhealthy: '五條纜繩沒有全綠，這條 Route 維持停用。修好下面紅的那一條，再按一次儲存。',
      failed: '沒有存進去。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
      nameRequired: '名稱不能空白：媒體庫頁的切換列與送單時的 Route 下拉都顯示它。',
    },
    recheck: '重新檢查',
    rechecking: '檢查中…',
    recheckFailed: '檢查沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    rechecked: '檢查跑完了。',
    delete: {
      label: '刪除這條 Route',
      confirm: '確定刪除',
      pending: '刪除中…',
      warning:
        '刪除之後這條 Route 的設定就不在了。qBittorrent 的分類與 complete 子目錄留著不動；之後用同一個名字重建時，分類檢查認得它們。',
      inUse:
        '{{jobs}}、{{files}}指著這條 Route，所以它刪不得。停用它，新的送單就不會再選到它；已經在路上的下載照常入庫。',
      inUseDisabled:
        '{{jobs}}、{{files}}指著這條 Route，所以它刪不得。它已經停用，新的送單不會選到它。',
      refused:
        '刪的那一刻發現還有 {{jobs}}、{{files}}指著這條 Route，所以它刪不得。停用它，新的送單就不會再選到它。',
      refusedUncounted:
        '刪的那一刻發現還有下載或入庫檔案指著這條 Route，所以它刪不得。停用它，新的送單就不會再選到它。',
      failed: '沒有刪掉。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
      done: '已刪除「{{name}}」。',
    },
    disable: {
      label: '停用這條 Route',
      pending: '停用中…',
      done: '已停用「{{name}}」：新的送單不會再選到它。',
      failed: '沒有停用。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    },
    add: {
      open: '新增 Route',
      title: '新增 Route',
      lede: '同一個 Jellyfin 媒體庫可以有好幾條 Route，每條寫到它自己的一條路徑。路徑是 Jellyfin 回報的，所以這裡用選的；Jellyfin 還沒有那條路徑的話，先在 Jellyfin 替媒體庫加上。',
      loading: '向 Jellyfin 問媒體庫清單…',
      library: '媒體庫',
      target: '寫入目標',
      taken: '已是「{{name}}」',
      noneFree: '這個媒體庫回報的路徑都已經有 Route 了。先在 Jellyfin 替它加一條路徑，再回來新增。',
      openJellyfin: '到 Jellyfin 替媒體庫加路徑',
      pickFirst: '先選一個媒體庫，與一條還沒有 Route 的寫入目標。',
      submit: '建立並檢查',
      submitting: '建立並檢查中…',
      createdOk: '已建立「{{name}}」：五條纜繩全綠，已經啟用。',
      createdRed:
        '已建立「{{name}}」，但五條纜繩沒有全綠，所以維持停用。修好掛載之後在它那一列重新檢查，再勾啟用。',
      unreachable: '問不到 Jellyfin 的媒體庫清單，而新增 Route 要用它回報的路徑。原文：',
      failed: '沒有建立。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
      refusal: {
        library_missing:
          'Jellyfin 上已經沒有這個媒體庫了。取消後重新打開這個區塊，清單會再問一次。',
        library_unsupported: 'Berth 只寫入電影與劇集類型的媒體庫。',
        target_not_in_library:
          '這條路徑已經不是這個媒體庫的了——Jellyfin 那邊剛改過。取消後重新打開這個區塊再選一次。',
        target_taken: '這條路徑剛被另一條 Route 用走了。每條 Route 要有自己的寫入目標。',
        route_conflict: '另一條 Route 在同一時間建立，這一條沒有存進去。再按一次「建立並檢查」。',
        jellyfin_unreachable: '建立的那一刻問不到 Jellyfin。確認它還在跑，再按一次。',
      },
    },
  },
  common: {
    expand: '展開',
    collapse: '收起',
    // 長清單一段底端的那一顆（M1.5 票 09）：說得出收起的是哪一段。
    collapseNamed: '收起 {{name}}',
    audits_one: '{{count}} 個待確認',
    audits_other: '{{count}} 個待確認',
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
    done_one: '{{count}} service decided',
    done_other: '{{count}} services decided',
  },
  service: {
    jellyfin: 'Jellyfin',
    qbittorrent: 'qBittorrent',
    prowlarr: 'Prowlarr',
  },
  status: {
    ok: 'Done',
    skipped: 'Already there',
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
    ip_banned: 'Has banned this machine (too many failed logins)',
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
    tmdb: 'TMDB',
    verified: 'Verified',
    unverified: 'Not verified',
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
    },
    version: {
      label: 'Too old',
      current: 'This Jellyfin is {{version}}; Berth needs 12.0 or newer.',
      why: 'From Jellyfin 12.0 the server itself folds the versions of one episode into a single entry. On 10.x that needed a third-party plugin, which on 12 does nothing and can merge across libraries. So Berth supports 12 and newer only. (12.0 is what would have been 10.12 — they dropped the leading 10.)',
      upgrade:
        'Before upgrading: back up Jellyfin’s /config in full — 12 changes the database and there is no way back except restoring that backup; then remove third-party plugins, since 10.11 plugins cannot load on 12. After upgrading: run one full library scan so the automatically grouped versions come back.',
    },
    step: {
      public_info: 'Confirm the version and that the startup wizard has not run',
      configuration: 'Language and metadata region',
      admin_user: 'Create the administrator from the Berth credentials',
      libraries: 'Create the Movies / TV / Anime libraries',
      remote_access: 'Enable remote access',
      complete: 'Finish the startup wizard',
      api_key: 'Create an API key for Berth',
    },
    bundled: {
      title: 'Take this Jellyfin over',
      lede: 'This Jellyfin has not run its own startup wizard, so Berth can do all of it. Every step is safe to press again: the ones already in the right shape are marked "already so" and are not redone.',
      run: 'Start mooring',
      rerun: 'Run it again',
      retry: 'Retry the failed step',
      running: 'Running…',
      done: 'This berth is secured. Jellyfin has the Berth administrator, the three libraries and an API key for Berth.',
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
    fix: {
      generic: 'Do this step by hand on your Jellyfin, then come back and retry.',
      public_info:
        'Check the Jellyfin container is running and on 12.0 or newer, then check the address and port were not changed:',
      configuration: "Set the language and metadata country in Jellyfin's own startup wizard:",
      admin_user:
        "Create the administrator in Jellyfin's own startup wizard, using the same credentials as step 1 here:",
      libraries:
        "Create the Movies, TV and Anime libraries by hand under Jellyfin's Libraries, with real-time monitoring off and Specials as the season-zero name:",
      remote_access: "Enable remote access in Jellyfin's startup wizard:",
      complete: "Finish Jellyfin's own startup wizard through to the last page:",
      api_key: "Create an API key named Berth under Jellyfin's API Keys:",
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
    title: 'Routes',
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
    build_one: 'Build {{count}} route and check',
    build_other: 'Build {{count}} routes and check',
    recheck_one: 'Check {{count}} route again',
    recheck_other: 'Check {{count}} routes again',
    requestFailed:
      'The request did not finish. The Berth backend may be down — check the container and press again.',
    routeMissing:
      'This step also re-checks the routes you already have, and one of them was deleted while it ran — another tab, most likely. Reload this step and the rest will be checked again.',
    cutaway: {
      paths: 'Paths',
      libraryRoot: 'Library root',
      completeRoot: 'Complete root',
      count: 'Routes to build this round',
      plan: 'Will create',
      library: 'Library',
      target: 'Write target',
      category: 'Category',
    },
    picker: {
      title: 'Pick the libraries',
      lede: 'One route per library. The paths come from Jellyfin, so you pick one instead of typing it.',
      target: 'Write target',
      mixed: 'Mixed',
      unsupported: 'Berth writes into movie and TV libraries only, so this one is skipped.',
      tvdb: 'This library has a TVDB metadata fetcher. Berth follows TMDB, and the two number seasons and episodes differently.',
      noPath: 'This library has no path on Jellyfin.',
      routed:
        'Already has a route: the wizard only adds, it never changes or deletes one. If it was a mistake, use the delete under that route below; once setup is done, manage routes under Settings → Routes.',
      addBerthPath: 'Add a Berth path',
      adding: 'Adding…',
      addHint:
        'Adds {{path}} to this library. Your existing paths stay where they are, and the new one becomes the write target.',
    },
    health: {
      unknown: 'Not checked',
      ok: 'Ready',
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
    needTmdb:
      'Step 6 is not finished: TMDB needs an API key that passes its test. Without it discovery, episode snapshots and naming all stop, so this step cannot be skipped.',
    needRoutes:
      'Step 7 is not finished: all five checks have to pass on every route. Submitting to a red one always fails.',
    unfinished:
      'A step is still unfinished, but this page cannot tell which. Go back a step and look at each berth — the red one is it.',
    fixTmdb: 'Go back and enter the TMDB key',
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
    label: 'Main',
    skip: 'Skip to content',
    discover: 'Discover',
    inventory: 'Library',
    jobs: 'Downloads',
    issues: 'Issues',
    review: 'Review',
    health: 'Health',
    settings: 'Settings',
    signOut: 'Sign out',
    signingOut: 'Signing out…',
  },
  discover: {
    trending: 'Trending this week',
    popular: 'Popular',
    results: 'Results for “{{query}}”',
    noArt: 'NO ART',
    tracked: 'Downloaded before',
    empty: 'TMDB returned nothing this round. Berth asks again once the hour-long cache expires.',
    off: 'Cannot reach the Berth backend. Check that the process is still running.',
    search: {
      label: 'Search titles',
      placeholder: 'A series or film, in any language',
      tooShort: 'Type {{min}} or more characters to search.',
      searching: 'Searching…',
      count_one: '{{count}} title',
      count_other: '{{count}} titles',
      none: 'Nothing here is called “{{query}}”. Try another spelling, or the original title.',
      back: 'Back to trending',
    },
    attribution: 'This product uses the TMDB API but is not endorsed or certified by TMDB.',
    tmdbLogo: 'TMDB logo',
  },
  watching: {
    resume: 'Continue watching',
    nextUp: 'Next up',
    count_one: '{{count}} item',
    count_other: '{{count}} items',
    showAll_one: 'Show all {{count}}',
    showAll_other: 'Show all {{count}}',
    showFewer: 'Show fewer',
    carryOn_one: 'Keep watching: {{count}}',
    carryOn_other: 'Keep watching: {{count}}',
    noArt: 'NO ART',
    down: "Berth can't reach Jellyfin, so Continue watching and Next up are unavailable for now.",
    retry: 'Retry',
    elsewhere: 'Continue watching and Next up are listed on page 1, without filters.',
    toFirst: 'See them on page 1',
  },
  inventory: {
    title: 'Library',
    libraries: 'Libraries',
    filters: 'Filter',
    filter: {
      all: 'All',
      review_one: 'Review {{count}}',
      review_other: 'Review {{count}}',
      unmatched_one: 'Unmatched {{count}}',
      unmatched_other: 'Unmatched {{count}}',
    },
    queue: {
      review: 'Review',
      unmatched: 'Unmatched',
      rest_one: '{{count}} more in the review queue',
      rest_other: '{{count}} more in the review queue',
    },
    sort: {
      label: 'Sort',
      order: 'Order',
      Ascending: 'Ascending',
      Descending: 'Descending',
      by: {
        SortName: 'Name',
        Random: 'Random',
        CommunityRating: 'Community rating',
        CriticRating: 'Critic rating',
        DateCreated: 'Date added',
        DateLastContentAdded: 'Date episode added',
        SeriesDatePlayed: 'Date played',
        DatePlayed: 'Date played',
        OfficialRating: 'Parental rating',
        PlayCount: 'Play count',
        PremiereDate: 'Release date',
        Runtime: 'Runtime',
      },
    },
    narrow: {
      genres: 'Genres',
      years: 'Years',
      chosen_one: '{{count}} chosen',
      chosen_other: '{{count}} chosen',
      loading: 'Loading…',
      none: {
        genres: 'No title in this library has a genre.',
        years: 'No title in this library has a year.',
      },
      failed: 'Cannot read the filter options for this library.',
      retry: 'Retry',
      clear: {
        genres: 'Clear genres',
        years: 'Clear years',
      },
      nothing: 'No title in this library matches the filter.',
      listed: {
        genres: 'Genres: {{list}}',
        years: 'Years: {{list}}',
        q: 'Name contains “{{q}}”',
      },
      clearBoth: 'Clear genres and years',
      clearSearch: 'Clear search',
    },
    search: {
      label: 'Find by name',
    },
    showing_one: 'Showing {{count}} item',
    showing_other: 'Showing {{count}} items',
    notInJellyfin: 'Not in Jellyfin yet',
    notInJellyfinCount_one: '{{count}} title not in Jellyfin yet',
    notInJellyfinCount_other: '{{count}} titles not in Jellyfin yet',
    pages: 'Pages',
    pagesEnd: 'Pages, end of wall',
    previous: 'Previous',
    next: 'Next',
    range: 'Titles {{first}}–{{last}} of {{total}}',
    rangeBeyond: 'This page is past the end; {{total}} titles in all',
    status: {
      failed: 'Failed',
      review: 'Review',
      downloading: 'Downloading',
      complete: 'Imported',
      partial: 'Partial',
      empty: 'No files',
    },
    episodes: '{{imported}} of {{aired}} episodes imported',
    versions_one: '{{count}} version',
    versions_other: '{{count}} versions',
    watch: {
      played: 'Watched',
      progress: '{{progress}}% watched',
      unplayed_one: '{{count}} episode unwatched',
      unplayed_other: '{{count}} episodes unwatched',
      markPlayed: 'Mark watched',
      markUnplayed: 'Mark unwatched',
      pending: 'Saving…',
      named: '{{action}}: {{subject}}',
      donePlayed: 'Marked as watched.',
      doneUnplayed: 'Marked as unwatched.',
      warningMovie:
        'This clears how many times you watched this film and when you last did. It cannot be brought back.',
      warningSeries:
        'This clears how many times you watched every episode of this show and when you last did, including episodes you watched on their own. It cannot be brought back.',
      warningEpisode:
        'This clears how many times you watched this episode and when you last did. It cannot be brought back.',
      warningProgress: 'This clears your place at {{progress}}%. It cannot be brought back.',
      warningSeriesPlayed:
        'Every episode is marked watched, and any episode you are partway through goes back to the start. It cannot be brought back.',
      refused: {
        item_not_visible: 'You cannot see this title in Jellyfin. Nothing was saved.',
        jellyfin_unreachable:
          'Berth cannot reach Jellyfin. Nothing was saved. Check on the Health page that Jellyfin is up, then press it again.',
        other:
          'Nothing was saved. Berth’s own API did not answer — check that it is still running, then press it again.',
      },
    },
    jellyfin: {
      open: 'Open in Jellyfin',
      openNamed: 'Open in Jellyfin: {{title}} (opens in a new tab)',
      itemNewTab: '{{name}} (opens in a new tab)',
      newTab: ' (opens in a new tab)',
      searching: 'Jellyfin is still scanning',
      lost: 'Jellyfin cannot find it',
      noAddress: 'Jellyfin’s address is unknown',
      downLabel: 'Jellyfin unreachable',
      down: 'Berth cannot reach Jellyfin, and the library needs it to know which libraries you can see and what is in them.',
      retry: 'Retry',
      toHealth: 'Open Health',
    },
    empty: {
      noLibraries: 'None of the libraries you can see in Jellyfin is a film or TV library.',
      askAdmin: 'Ask an administrator to share a library with you in Jellyfin.',
      openJellyfin: 'Open Jellyfin’s library settings',
      library: '“{{library}}” has no titles yet.',
      toDiscover: 'Back to Discover',
      page: 'There are no titles on this page.',
      toFirstPage: 'Back to page 1',
      review: 'No downloads for this library are waiting for review.',
      unmatched: 'No files for this library are unmatched.',
      showAll: 'Show all',
      unknown: 'This library does not exist, or you do not have access to it.',
      toFirst: 'Open “{{library}}”',
    },
    off: 'Cannot read the library. Berth’s own API did not answer — check that it is still running.',
  },
  media: {
    aired: 'First aired {{date}}',
    released: 'Released {{date}}',
    tmdbId: 'TMDB {{id}}',
    folderPreview: 'Folder will be',
    awaitingReview_one:
      '{{count}} download for this title is waiting for an administrator to review it.',
    awaitingReview_other:
      '{{count}} downloads for this title are waiting for an administrator to review them.',
    folderNote:
      'This name is fixed the moment a download goes through; a later TMDB rename will not move it.',
    folderFrozen: 'Folder',
    folderFrozenNote:
      'This name was fixed when the first download went through; a later TMDB rename will not move it.',
    tracked: 'Downloaded before',
    seasons: 'Seasons and imports',
    backToDiscover: 'Back to Discover',
    stale: 'Stale snapshot',
    fetchedAt: 'Snapshot taken',
    refresh: 'Refresh now',
    refreshing: 'Refreshing…',
    minutes_one: '{{count}} minute',
    minutes_other: '{{count}} minutes',
    minutesShort_one: '{{count}}m',
    minutesShort_other: '{{count}}m',
    season: {
      count_one: '{{count}} season',
      count_other: '{{count}} seasons',
      empty: 'TMDB has no episodes for this season yet. They arrive once it airs.',
      film: 'Films have no seasons.',
      none: 'TMDB lists no seasons for this title yet.',
      missingOnly: 'Missing only',
      numbering: 'Seasons and episodes follow TMDB’s numbering, as do the imported file names.',
      numberingWatched:
        'Seasons and episodes follow TMDB’s numbering, as do the imported file names. Watch above uses Jellyfin’s, and the numbers may differ.',
      missingTotal_one: '{{count}} episode missing',
      missingTotal_other: '{{count}} episodes missing',
      noneMissingAnywhere: 'Nothing missing',
      missing_one: '{{count}} missing',
      missing_other: '{{count}} missing',
      noneMissing: 'None missing',
      noneMissingHere: 'Nothing is missing from this season.',
      searchMissing: 'Search for the missing episodes',
      searchMissingSeason: 'Search for what {{season}} is missing',
    },
    episode: {
      count_one: '{{count}} episode',
      count_other: '{{count}} episodes',
      number: 'Ep',
      name: 'Title',
      absolute: 'Abs',
      runtime: 'Runtime',
      airDate: 'Aired',
      caption: 'Episodes of {{season}}',
      runtimeValue: 'Runtime {{value}}',
      airDateValue: 'Aired {{value}}',
      inLibrary: 'In library',
      state: {
        imported: 'Imported',
        downloading: 'Downloading',
        stuck: 'Stuck',
        missing: 'Missing',
        unaired: 'Not aired',
      },
    },
    files: {
      title: 'Files and versions',
      count_one: '{{count}} file',
      count_other: '{{count}} files',
      total_one: '{{count}} file in total',
      total_other: '{{count}} files in total',
      none: 'Nothing has been imported yet.',
      special: 'Special',
      tags: 'Tags',
      target: 'Target',
      action: {
        import: 'Feature',
        extra: 'Extra',
        subtitle: 'Subtitle',
        skip: 'Skipped',
        unmatched: 'Unmatched',
        review: 'Review',
      },
      ledger: {
        label: 'Ledger',
        ok: 'Matches',
        allOk: 'Ledger matches',
        off_one: '{{count}} ledger entry off',
        off_other: '{{count}} ledger entries off',
        target_missing: 'The library file is gone',
        source_missing: 'The source in complete is gone',
        inode_mismatch: 'No longer the same inode',
        unlinked: 'Removed from the library when deleted',
      },
      jellyfin: {
        found: 'In Jellyfin',
        searching: 'Jellyfin is still scanning; next look',
        foundCount_one: '{{count}} in Jellyfin',
        foundCount_other: '{{count}} in Jellyfin',
        searchingCount_one: '{{count}} still scanning',
        searchingCount_other: '{{count}} still scanning',
        lostCount_one: '{{count}} not found by Jellyfin',
        lostCount_other: '{{count}} not found by Jellyfin',
        lost_one: 'Jellyfin did not show it after {{count}} try',
        lost_other: 'Jellyfin did not show it after {{count}} tries',
      },
      versions: {
        title: 'Versions side by side',
        noneTv: 'Every episode has a single version.',
        noneMovie: 'This film has a single version.',
        note: 'In Jellyfin these versions share one entry with a version menu. Jellyfin decides the names and the order in that menu; what you see here is what it reports.',
        pending:
          'Versions Jellyfin has not indexed yet have no name, so the tags from the file name are shown instead.',
      },
      unmatched: {
        title: 'Unmatched files',
        note: 'The parser could not tie these to any episode, so they stay where they are in complete and are not imported. You can assign one to an episode, mark it as an extra or ignore it.',
        pending: 'This download’s plan is still waiting for review; decide it in the review queue.',
        toJobs: 'See downloads',
      },
    },
    route: {
      label: 'Import into',
      none: 'Not chosen',
      toSetup: 'Create a route in the setup wizard',
      askAdmin: 'Ask an administrator to create a route that can take it.',
      missing: {
        tv: 'No route accepts series yet. Without one a finished download has nowhere to land.',
        movie: 'No route accepts films yet. Without one a finished download has nowhere to land.',
      },
    },
  },
  watch: {
    title: 'Watch',
    resume: 'Resume {{code}}',
    next: 'Play next {{code}}',
    first: 'Start with {{code}}',
    film: 'Watch in Jellyfin',
    filmResume: 'Resume',
    open: 'Open in Jellyfin',
    allWatched: 'All watched',
    seasons: 'Seasons',
    chipResume: 'Resume',
    chipNext: 'Next',
    noSeasons: 'Jellyfin has no episodes of this show yet.',
    emptySeason: 'Jellyfin has no episodes in this season yet.',
    failed: 'The episodes of this season could not be read.',
    retry: 'Try again',
    down: 'Berth cannot reach Jellyfin, so the watch area is unavailable for now.',
  },
  search: {
    title: 'Search torrents',
    keyword: 'Keyword',
    keywordPlaceholder: "Leave empty to use the title's own names",
    keywordPlaceholderMissing: 'Leave empty to ask for the missing episodes',
    submit: 'Search',
    submitting: 'Searching…',
    willAskMissing: 'Berth will ask for the episodes this title is missing:',
    willAskMissingSeason: 'Berth will ask for the episodes {{season}} is missing:',
    missingOff: 'Search by title instead',
    willAsk: 'Berth will ask for each of these names:',
    answeredAll_one: '{{count}} keyword answered',
    answeredAll_other: 'All {{count}} keywords answered',
    answeredRest_one: '{{count}} other keyword answered',
    answeredRest_other: '{{count}} other keywords answered',
    willAskTyped: 'Berth will ask for this only:',
    slow: 'The indexer contacts every tracker it knows, which usually takes about a minute.',
    count_one: '{{count}} result',
    count_other: '{{count}} results',
    countCapped: '{{total}} results · {{shown}} taken across the sites',
    empty:
      'None of those keywords turned up anything on your indexer. Try wording it yourself, or search again later — what public sites carry changes.',
    onlyOthers_one:
      "The indexer returned {{count}} release, but none of them carries this title's name. Try typing a keyword yourself.",
    onlyOthers_other:
      "The indexer returned {{count}} releases, but none of them carries this title's name. Try typing a keyword yourself.",
    discarded_one: "{{count}} more release did not carry this title's name and was skipped.",
    discarded_other: "{{count}} more releases did not carry this title's name and were skipped.",
    off: "The search never went out. Berth's own API did not answer; check that it is still running.",
    announce_one: 'Found {{count}} result; {{failed}} keywords went unanswered.',
    announce_other: 'Found {{count}} results; {{failed}} keywords went unanswered.',
    column: {
      title: 'Release',
      size: 'Size',
      seeders: 'Seeders',
      indexer: 'Source',
      estimate: 'Estimate',
    },
    seedersInline_one: '{{value}} seeder',
    seedersInline_other: '{{value}} seeders',
    sort: {
      label: 'Sort by',
    },
    estimate: {
      wholeSeason: 'Full season',
      unknown: 'Cannot tell',
      movie: 'Film',
    },
    problem: {
      not_configured: {
        label: 'Not connected',
        body: 'Step 5 of the setup wizard skipped the indexer, so Berth has nowhere to search. Connect Prowlarr or any Torznab endpoint and this section comes alive.',
      },
      no_query: {
        label: 'Nothing to ask',
        body: 'Berth has no TMDB snapshot for this title yet, so it does not know what names to ask for. Hit Refresh now above, or type a keyword yourself.',
      },
      no_search: {
        label: 'No search offered',
        body: 'This Torznab endpoint reports that it does not offer search. The address and key are fine; it simply cannot do this. Use another endpoint.',
      },
      credential_rejected: {
        label: 'Credential rejected',
        body: 'The indexer rejected this API key. It may have been rotated, or lost a few characters on the way in.',
      },
      unreachable: {
        label: 'Unreachable',
        body: 'Cannot reach the indexer. Either its container is not running, or the address is wrong.',
      },
      toSetup: 'Open the setup wizard',
      askAdmin: 'Ask an administrator to connect an indexer in the setup wizard.',
    },
  },
  issues: {
    title: 'Issues',
    count_one: '{{count}} issue',
    count_other: '{{count}} issues',
    empty: 'Nothing to decide. At the last reconcile the ledger and the disk agreed.',
    emptyNeverRun: 'Nothing to decide. No reconcile has run since this process started.',
    off: 'Could not read the issue list. Berth’s own API did not answer — check that it is still running.',
    detectedAt: 'Found {{value}}',
    target: 'Library path',
    completePath: 'Complete path',
    source: 'Source path',
    job: 'Download',
    measuredPath: 'Measured folder',
    library: 'Jellyfin library',
    fetchers: 'TVDB fetcher',
    free: 'Free',
    minFree: 'Threshold',
    next: 'Next step',
    nextTvdb:
      'Remove the TVDB metadata fetcher in the Jellyfin library settings. Berth names files after TMDB, and TVDB may number seasons and episodes differently. Once it is gone, the next health check (within 5 minutes) closes this on its own; if you use TVDB on purpose, press Ignore and it will not ask again.',
    nextDisk:
      'Free up space, or change the threshold in the service settings. Once there is room again, the next health check closes this on its own.',
    type: {
      library_link_missing: 'This file is missing from the library',
      source_missing: 'The source file under complete is gone',
      inode_mismatch: 'The target and the source are not the same data',
      orphan_complete: 'A folder under complete belongs to nothing',
      unknown_torrent: 'qBittorrent holds a torrent Berth does not know',
      unmanaged_library_file: 'The library holds a file Berth does not know',
      job_without_files: 'This job imported, but its ledger is empty',
      missing_files: 'qBittorrent reports the files as missing',
      client_error: 'qBittorrent reports an error',
      client_removed: 'The torrent is no longer in qBittorrent',
      jellyfin_item_unresolved: 'Jellyfin never picked this file up',
      library_uses_tvdb: 'This route’s library uses TVDB',
      low_disk_space: 'Free disk space is below the threshold',
    },
    typeLabel: {
      library_link_missing: 'LINK MISSING',
      source_missing: 'SOURCE MISSING',
      inode_mismatch: 'INODE MISMATCH',
      orphan_complete: 'ORPHAN FOLDER',
      unknown_torrent: 'UNKNOWN TORRENT',
      unmanaged_library_file: 'UNMANAGED FILE',
      job_without_files: 'EMPTY LEDGER',
      missing_files: 'FILES MISSING',
      client_error: 'CLIENT ERROR',
      client_removed: 'REMOVED',
      jellyfin_item_unresolved: 'NOT IN JELLYFIN',
      library_uses_tvdb: 'TVDB',
      low_disk_space: 'LOW DISK',
    },
    action: {
      relink: 'Link it again',
      forget: 'Accept the deletion',
      delete_complete: 'Delete the download too',
      mark_sourceless: 'Mark as sourceless',
      replace_with_link: 'Replace with a hard link',
      delete_orphan: 'Delete this folder',
      replan: 'Plan it again',
      relook: 'Look it up again',
      rescan: 'Scan the libraries',
      recheck: 'Recheck',
      accept_loss: 'Accept the loss',
      retry: 'Retry',
      resubmit: 'Send it again',
      accept_removal: 'Accept the removal',
      adopt: 'Import it again',
      claim_torrent: 'Claim it as a download',
      claim_file: 'Claim it into the ledger',
      ignore: 'Ignore',
    },
    working: 'Working…',
    done: 'Done; it is off the list.',
    confirmDelete:
      'This removes everything belonging to this download: the links still in the library, the torrent in qBittorrent, the files under complete, and its ledger and records. The space only comes back once the source and every link are gone.',
    confirmDeleteAction: 'Delete it',
    confirmDeleteOrphan:
      'This deletes this whole folder under complete and every file in it. Neither qBittorrent nor Berth knows it; Berth checks once more that it still has no owner before it deletes.',
    confirmReplace:
      'The copy in the library is swapped for a hard link to the source. Both are the same size, but the copy itself goes away — if it is someone’s edited version, do not press this.',
    confirmReplaceAction: 'Replace it',
    refusal: {
      issue_missing: 'This issue is no longer there. Reload the page.',
      issue_not_open: 'This one has already been dealt with — most likely from another tab.',
      action_not_available:
        'That button does not apply here: this issue no longer points at a ledger row, or its download is gone or no longer in the state this issue describes.',
      source_missing:
        'The source under complete is gone too, so there is nothing to link. Either accept the deletion or download it again.',
      relink_failed: 'The link was not created.',
      client_unreachable:
        'qBittorrent did not answer, so nothing was done. Check that it is still running.',
      reconcile_running: 'A reconcile run is still going. Wait for it to finish.',
      in_use:
        'This folder has an owner now (a torrent in qBittorrent points at it, or Berth knows it), so it was not deleted.',
      size_differs:
        'The library copy and the source are no longer the same size — most likely it was re-encoded — so it was not replaced.',
      jellyfin_unreachable:
        'Jellyfin was not asked to scan, and this file was not queued for another lookup. Check on the health page that Jellyfin is still there.',
      delete_failed: 'The folder was not deleted.',
      source_unavailable:
        'The saved download link no longer gives the same torrent (the indexer link has most likely expired), so nothing was sent. Search for it again from the media page.',
      resubmit_failed:
        'It was sent, and qBittorrent refused it. Once that is fixed, pressing again sends it again.',
      route_unusable:
        'This download’s route cannot be used right now (deleted, disabled or failing), so it could not be imported anyway. Check that route in the library path settings first.',
      media_required:
        'Pick which title this is first. A download without a title has no target path to go to.',
      unclaimable: 'It does not match the ledger, so nothing was written.',
    },
    claimMiss: {
      outside_routes: 'It is not under any route’s target.',
      no_source:
        'No file in complete is the same data as this one: it is a copy, or its source was deleted long ago. Download it again to import it.',
      unknown_work:
        'The title folder does not say which TMDB title it is (no [tmdbid-…], or TMDB could not be asked).',
      not_berth_naming:
        'Its name is not one Berth’s naming templates would write (it was renamed, or the episode’s TMDB name changed). Import it again from complete to get it into the ledger.',
    },
    unclaimedBecause: 'Why it did not match',
    pick: {
      label: 'Which title is this',
      placeholder: 'Type a title to search TMDB',
      searching: 'Searching…',
      none: 'Nothing found. Try another name.',
      off: 'TMDB could not be searched. Check on the health page that its credential still works.',
      confirm: 'Import into {{title}}',
      cancel: 'Cancel',
      tv: 'Series',
      movie: 'Film',
    },
    failed:
      'That did not go through. Berth’s own API did not answer — check that it is still running.',
  },
  review: {
    title: 'Review',
    count_one: '{{count}} item',
    count_other: '{{count}} items',
    truncated: 'Showing the oldest {{shown}} of {{total}}.',
    empty: 'Nothing is waiting for you.',
    off: 'Could not read the review queue. Berth’s own API did not answer — check that it is still running.',
    section: {
      decide: 'Needs a decision',
      look: 'In the library, awaiting a look',
    },
    issues_one: '{{count}} more issue is waiting',
    issues_other: '{{count}} more issues are waiting',
    plan: {
      label: 'NEEDS REVIEW',
      reason: {
        low_confidence: 'Some files need you to confirm their season and episode',
        medium_not_allowed: 'This library route holds medium confidence for your nod',
        nothing_to_import: 'Nothing here would reach the library — most likely the wrong torrent',
        target_exists: 'Another file already sits at a target in the library',
        audit_undone: 'An auto-imported file was undone; that row needs a new decision',
      },
      waitingSince: 'Waiting since {{value}}',
      job: 'Download',
      loading: 'Reading the plan…',
      off: 'Could not read this plan.',
      held_one: '{{count}} row needs you',
      held_other: '{{count}} rows need you',
      rest_one: 'The other {{count}} file',
      rest_other: 'The other {{count}} files',
      lands: 'On approval, lands at',
      landed: 'Already in the library',
      nowhere: 'Stays out of the library on approval',
      noProposal: 'No season or episode yet — change this row first',
      edit: 'Change',
      apply: 'Apply',
      cancel: 'Cancel',
      field: {
        action: 'Decision',
        season: 'Season',
        start: 'From episode',
        end: 'To episode',
      },
      endHint: 'Empty for one episode',
      applied: 'Applied; the target path is updated.',
      approve: 'Approve and import',
      reject: 'Reject',
      confirmReject:
        'This throws the plan away, including rows you changed, and Berth plans it again. No file is touched.',
      confirmRejectAction: 'Reject it',
      working: 'Working…',
      approved: 'Approved; importing now.',
      rejected: 'Rejected; Berth is planning it again.',
      failed:
        'That did not go through. Berth’s own API did not answer — check that it is still running.',
      refusal: {
        plan_missing: 'This plan is gone — most likely a replan replaced it.',
        not_pending:
          'This plan is no longer waiting — most likely another tab approved or rejected it.',
        item_missing: 'That row is no longer in this plan.',
        item_applied: 'That row is already in the library; changing it takes a rematch.',
        action_not_allowed: 'That decision contradicts what kind of file this is.',
        episode_required: 'To import it, fill in the season and the first episode.',
        episode_range_reversed: 'The last episode comes before the first.',
        episode_not_allowed: 'Only an imported episode has a season and episode to fill in.',
        media_missing: 'This plan has no title data, so there is nowhere to write it.',
        target_clash: 'Two rows would be written to one path; change one of them first:',
        undecided: 'Some rows are still undecided — import, skip or unmatch them first:',
      },
    },
    audit: {
      label: 'UNCONFIRMED',
      reason: {
        medium_auto_imported: 'Medium confidence, imported automatically',
      },
      because: 'Medium confidence: {{lead}}',
      lead: {
        title_mismatch: 'the release title does not look like this title',
        strategy_outlier: 'the rest of this batch was read by {{strategy}}, this one was not',
        single_season: 'the season was inferred (TMDB has only one season)',
        season_from_arc: 'the season was inferred from an arc name',
        final_season: 'the season was inferred (“final season” taken as the last one)',
        air_date_run: 'the season was worked out by splitting air dates into runs',
        cour_offset: 'the episode was worked out (a later part of the season)',
        absolute_group: 'the episode was worked out (TMDB absolute numbering)',
        absolute_cumulative: 'the episode was worked out (season lengths added up)',
        specials_numbering: 'the group’s special numbering may not match TMDB',
      },
      group: {
        same_one: '{{count}} file, medium confidence: {{lead}}',
        same_other: '{{count}} files, medium confidence: {{lead}}',
        none_one: '{{count}} file at medium confidence, imported automatically',
        none_other: '{{count}} files at medium confidence, imported automatically',
        mixed_one:
          '{{count}} file at medium confidence for more than one reason — expand to see each',
        mixed_other:
          '{{count}} files at medium confidence for more than one reason — expand to see each',
      },
      confirmAll: 'Confirm all',
      confirmSection_one:
        'The {{count}} imported file listed in this section is marked as right; no file is touched. Anything that arrives after you press this is not included.',
      confirmSection_other:
        'The {{count}} imported files listed in this section are marked as right; no file is touched. Anything that arrives after you press this is not included.',
      confirmSectionAction_one: 'Confirm {{count}} file',
      confirmSectionAction_other: 'Confirm {{count}} files',
      confirmedMany_one: 'Confirmed {{count}} file; it is off the queue.',
      confirmedMany_other: 'Confirmed {{count}} files; they are off the queue.',
      skipped_one: '{{count}} had already been confirmed or undone elsewhere and was skipped.',
      skipped_other: '{{count}} had already been confirmed or undone elsewhere and were skipped.',
      importedAt: 'Imported {{value}}',
      target: 'Library path',
      source: 'Source path',
      job: 'Download',
      reasons: 'Parser reasons',
      action: {
        confirm: 'Confirm',
        undo: 'Undo',
      },
      confirmUndo:
        'This takes the episode out of the library, so Jellyfin drops it on its next scan. The files under complete stay; the download goes back to review.',
      confirmUndoAction: 'Undo the import',
      working: 'Working…',
      refusal: {
        ledger_missing: 'This row is gone — most likely undone from another tab.',
        not_audited: 'This one has already been confirmed — most likely from another tab.',
        unlink_failed: 'The file in the library could not be removed, so nothing changed.',
      },
      failed:
        'That did not go through. Berth’s own API did not answer — check that it is still running.',
      confirmed: 'Confirmed; it is off the queue.',
      undone: 'Undone; the download is back in review.',
      undoneUnmanaged:
        'Undone; the download is back in review. The file in the library is no longer the one Berth put there, so it was not deleted.',
    },
    unmatched: {
      label: 'UNMATCHED',
      reason: {
        left_in_place: 'Matches no episode; left in place under complete',
      },
      waitingSince: 'Planned {{value}}',
      path: 'Source path',
      job: 'Download',
      reasons: 'Parser reasons',
    },
    duplicate: {
      label: 'DUPLICATE',
      reason: {
        same_version: 'The library already has this episode with the same tags',
        span_clash:
          'The library already has a file that starts at the same episode but covers a different range. Keeping both lets Jellyfin 12 fold them into two versions of one episode, and the later episode disappears from the list',
      },
      skippedAt: 'Skipped {{value}}',
      path: 'New file',
      known: 'In the library',
      job: 'Download',
      action: {
        replace: 'Replace the old one',
        keep_both: 'Keep both',
        skip: 'Skip',
      },
      confirmReplace:
        'The version in the library comes out and this one takes its place; the old version’s subtitles go with it. Nothing under complete is touched.',
      confirmReplaceAction: 'Replace it',
      confirmKeepClash:
        'Both stay in the library: Jellyfin 12 folds them into two versions of one episode, and the later episode disappears from the list.',
      confirmKeepClashAction: 'Keep both anyway',
      keepBothHint:
        'Keeping both adds a number tag ([2]) to the new file name; Jellyfin shows it as another version of the same episode.',
      working: 'Working…',
      failed:
        'That did not go through. Berth’s own API did not answer — check that it is still running.',
      done: {
        replace: 'Replaced; the library now has the new one.',
        keep_both: 'Both are in the library now.',
        skip: 'Skipped; this one stays under complete.',
      },
    },
  },
  rematch: {
    fix: 'Fix',
    field: {
      action: 'Change to',
      season: 'Season',
      start: 'First episode',
      end: 'Last episode',
    },
    endHint: 'Leave empty for one episode',
    action: {
      import: 'Assign to an episode',
      importMovie: 'Import',
      extra: 'Mark as extra',
      skip: 'Ignore',
    },
    apply: 'Apply',
    cancel: 'Cancel',
    working: 'Working…',
    confirmMove:
      'The file leaves its current place in the library and moves to the new one; its subtitles follow. Nothing under complete is touched.',
    confirmExtra:
      'It moves to the extras folder; extras carry no subtitles, so its subtitles come out. Nothing under complete is touched.',
    confirmDrop:
      'This takes it out of the library along with its subtitles. Nothing under complete is touched.',
    confirmAction: 'Apply the fix',
    done: 'Fixed.',
    failed:
      'That did not go through. Berth’s own API did not answer — check that it is still running.',
    refusal: {
      ledger_missing: 'This file’s ledger row is gone — most likely changed from another tab.',
      file_missing: 'This file is no longer part of that download.',
      not_unmatched: 'This file is no longer unmatched — most likely decided from another tab.',
      plan_pending: 'This download’s plan is still waiting for review; change the row there first.',
      not_duplicate: 'This row is no longer waiting — most likely decided from another tab.',
      action_not_allowed: 'That decision contradicts what kind of file this is.',
      episode_required: 'To assign it, fill in the season and the first episode.',
      episode_range_reversed: 'The last episode comes before the first.',
      episode_not_allowed: 'Only an episode assignment has a season and episode to fill in.',
      media_missing: 'This file has no title data, so there is nowhere to write it.',
      route_missing: 'The library route for this title is gone.',
      target_taken: 'Another file already sits at the target, and Berth does not overwrite it:',
      link_failed: 'The link could not be made, so nothing changed:',
      unlink_failed: 'The old link in the library could not be removed, so nothing changed:',
    },
  },
  reconcile: {
    start: 'Reconcile now',
    running: 'Reconciling…',
    lastRun: 'Last run {{time}}',
    opened_one: '{{count}} opened',
    opened_other: '{{count}} opened',
    updated_one: '{{count}} updated',
    updated_other: '{{count}} updated',
    neverRun: 'No reconcile has run since this process started.',
    sides: 'Reconcile progress',
    side: {
      ledger: 'Ledger',
      client: 'qBittorrent',
      complete: 'COMPLETE',
      library: 'Library',
      jellyfin: 'Jellyfin',
    },
    counted_one: '{{count}} checked',
    counted_other: '{{count}} checked',
    unavailable: 'Could not ask',
    skipped: 'Skipped {{value}}',
    failed:
      'The run did not start. Berth’s own API did not answer — check that it is still running.',
  },
  jobs: {
    title: 'Downloads',
    count_one: '{{count}} job',
    count_other: '{{count}} jobs',
    empty:
      'Nothing has been sent to download yet. Find a title on the discover page, search it for torrents, and send one.',
    toDiscover: 'Back to discover',
    off: 'Could not read the download list. Berth’s own API did not answer — check that it is still running.',
    media: 'Title',
    hash: 'info hash',
    sizeInline: 'Size {{value}}',
    progressInline: 'Progress {{value}}',
    retry: 'Send again',
    retrying: 'Sending…',
    retryImport: 'Retry the import',
    retryingImport: 'Importing…',
    retried: 'Retried; it is now {{state}}.',
    retryOff:
      'The retry was not sent. Berth’s own API did not answer — check that it is still running.',
    reimport: 'Import again',
    reimporting: 'Importing again…',
    reimportOff:
      'The reimport was not sent. Berth’s own API did not answer — check that it is still running.',
    reimported: 'Queued to import again; it is now {{state}}.',
    waitingForAdmin: 'Waiting for an administrator to review',
    toReview: 'Handle it in the review queue',
    detail: {
      open: 'Download details',
      back: 'Back to downloads',
      sentBy: 'Sent by',
      nobody: 'Nobody',
      error: 'What the service said',
      files: 'Files and decisions',
      noPlan: 'No plan yet: Berth works one out once the file list is in.',
      history: 'Plan history',
      historyEmpty: 'Nothing has been recorded for this plan yet.',
      timeline: 'Timeline',
      loading: 'Reading this download…',
      missing: 'No such download',
      missingHint:
        'The address may be mistyped, or the download was deleted along with its records.',
      off: 'Could not read this download. Berth’s own API did not answer — check that it is still running.',
    },
    state: {
      requested: 'Created',
      submitted: 'Sent',
      submit_failed: 'Send failed',
      metadata_ready: 'File list in',
      downloading: 'Downloading',
      stalled: 'Stalled',
      missing_files: 'Files missing',
      client_error: 'Client error',
      client_removed: 'Gone from client',
      completed: 'Download done',
      planning: 'Planning',
      review: 'Needs review',
      importing: 'Importing',
      imported: 'Imported',
      import_failed: 'Import failed',
      removed: 'Removed',
    },
    trigger: {
      manual: 'Manual',
      rss: 'RSS',
      reimport: 'Reimport',
    },
    event: {
      created: 'Created',
      submitted: 'Sent',
      submit_failed: 'Send failed',
      metadata_received: 'File list',
      progress: 'Progress',
      stalled: 'Stalled',
      completed: 'Downloaded',
      issue_detected: 'Needs you',
      retried: 'Retried',
      preplan: 'Estimate',
      plan_generated: 'Plan',
      review_required: 'Needs review',
      review_decided: 'Reviewed',
      linked: 'Linked',
      link_failed: 'Link failed',
      jellyfin_scan_requested: 'Jellyfin told',
      jellyfin_item_resolved: 'In Jellyfin',
      jellyfin_request_failed: 'Jellyfin request failed',
      deleted: 'Deleted',
      audit_confirmed: 'Confirmed',
      audit_undone: 'Import undone',
      rematched: 'Rematched',
      duplicate_skipped: 'Duplicate skipped',
      duplicate_decided: 'Duplicate decided',
      recovered: 'Picked back up',
      round_failed: 'Failed to process',
    },
    timeline: {
      loading: 'Reading the timeline…',
      empty: 'Nothing has happened to this job yet.',
      off: 'Could not read the timeline.',
      earlier_one: 'The {{count}} earlier event is on the details page.',
      earlier_other: 'The {{count}} earlier events are on the details page.',
      retried: 'Back to created, then sent again.',
      retriedImport: 'Back to importing; it picks up from the files not linked yet.',
      retriedRecheck: 'qBittorrent was asked to recheck the files and carry on downloading.',
      retriedRestart: 'qBittorrent was asked to start this one again.',
      retriedReplan: 'Back to downloaded, to be planned again.',
      retriedReimport: 'Reimported: planned again from the files in complete as they are now.',
      linkedFiles_one: '{{count}} file',
      linkedFiles_other: '{{count}} files',
      linkedTargets: 'List the targets',
      scanRequested_one: 'told about {{count}} file path',
      scanRequested_other: 'told about {{count}} file paths',
      resolved_one: 'found {{count}} file in Jellyfin',
      resolved_other: 'found {{count}} files in Jellyfin',
      jellyfin: {
        scan: 'The notice did not get through. Jellyfin’s own scheduled scan will catch up.',
      },
      files_one: '{{count}} file · {{size}}',
      files_other: '{{count}} files · {{size}}',
      resumed: 'moving again',
      idle_one: 'idle for {{count}} minute',
      idle_other: 'idle for {{count}} minutes',
      review: {
        low_confidence: 'some files could not be placed',
        medium_not_allowed: 'this route does not auto-import medium',
        nothing_to_import: 'nothing would reach the library',
        target_exists: 'another file already sits at the target',
        audit_undone: 'an auto-imported file was undone',
      },
      reviewApproved_one: 'An administrator approved it; {{count}} file will be imported',
      reviewApproved_other: 'An administrator approved it; {{count}} files will be imported',
      reviewRejected: 'An administrator rejected this plan; Berth plans it again',
      auditConfirmed: 'An administrator looked at this medium-confidence import and confirmed it',
      auditUndone: 'An administrator undid this file’s import; the job is back in review',
      auditUndoneGone:
        'An administrator undid this file’s import (it had already left the library); the job is back in review',
      auditUndoneUnmanaged:
        'An administrator undid this file’s import; the job is back in review. The file in the library is no longer the one Berth put there, so it was not deleted',
      keptUnmanaged_one:
        '{{count}} library file is no longer the one Berth put there and was not deleted:',
      keptUnmanaged_other:
        '{{count}} library files are no longer the ones Berth put there and were not deleted:',
      rematched: 'An administrator changed this file: {{from}} → {{to}}',
      notInLibrary: 'not in the library',
      duplicateSkipped_one:
        '{{count}} file duplicates one already in the library; skipped until you decide in the review queue',
      duplicateSkipped_other:
        '{{count}} files duplicate ones already in the library; skipped until you decide in the review queue',
      duplicateDecided: {
        replace: 'An administrator replaced the version in the library with this one',
        keep_both: 'An administrator kept both versions in the library',
        skip: 'An administrator passed on this duplicate; it stays under complete',
      },
      deletedLinks_one: 'removed {{count}} link',
      deletedLinks_other: 'removed {{count}} links',
      deletedSources_one: 'deleted {{count}} downloaded file',
      deletedSources_other: 'deleted {{count}} downloaded files',
      deletedTorrent: 'removed from qBittorrent',
      deletedPurged: 'records cleared',
      freed: 'freed {{size}}',
      freedNothing: 'Nothing was freed: another name still points at the same data.',
      recovered: {
        submit_failed: 'qBittorrent had taken this one after all; downloading carries on.',
        missing_files: 'The files are back in qBittorrent; downloading carries on.',
        client_error: 'The error in qBittorrent cleared; downloading carries on.',
        client_removed: 'This one is back in qBittorrent; downloading carries on.',
      },
      roundFailed: 'Berth failed while processing this one and will try again next round:',
      issue: {
        missing_files: 'qBittorrent says the files are gone. Force a recheck in its own UI.',
        client_error: 'qBittorrent reported an error of its own. Its UI or log says which one.',
        client_removed:
          'The torrent left qBittorrent. The downloaded files may still be where it left them.',
        unknown_torrent:
          'When this torrent turned up in qBittorrent, Berth had no download for it — added straight in qBittorrent, or left over from a restored database.',
        jellyfin_item_unresolved:
          'Jellyfin never listed these imported files. Most likely it cannot see this path, or it matched the folder to a different title — look for them in the Jellyfin library.',
      },
    },
    plan: {
      title: 'Import plan',
      loading: 'Reading the plan…',
      off: 'Could not read this plan.',
      planned_one: '{{count}} file will be imported',
      planned_other: '{{count}} files will be imported',
      files_one: '{{count}} file',
      files_other: '{{count}} files',
      levels: 'Confidence high {{high}} / medium {{medium}} / low {{low}}',
      estimate:
        'An estimate made while the download runs — nothing has read the files themselves yet. Berth works it out again once the download finishes.',
      status: {
        preplan: 'Estimate',
        auto: 'Importing by itself',
        pending_review: 'Needs review',
        approved: 'Approved',
        rejected: 'Rejected',
        applied: 'Applied',
        failed: 'Failed',
      },
      reason: {
        low_confidence:
          'Some files could not be placed in a season and episode, or the count does not match TMDB. An administrator confirms the rows in the review queue and approves; if TMDB has just caught up, plan it again.',
        medium_not_allowed:
          'This library route does not import medium-confidence files by itself, so the whole plan stopped for a person to look at. Once an administrator approves it in the review queue, it imports.',
        nothing_to_import:
          'Nothing in this torrent would reach the library. Most likely the wrong torrent was sent.',
        target_exists:
          'A file Berth did not link already sits at this spot in the library, and Berth will not overwrite it; the other files are already in. Move that file away, or skip that row in the review queue, then approve.',
        audit_undone:
          'An administrator undid a medium-confidence import from the review queue: that file has left the library, and its source under complete is untouched. The plan is back, waiting for someone to decide which episode that row really is.',
      },
      action: {
        import: 'Import',
        extra: 'Extra',
        subtitle: 'Subtitle',
        skip: 'Skip',
        unmatched: 'Unmatched',
        review: 'Review',
      },
      confidence: {
        high: 'High',
        medium: 'Medium',
        low: 'Low',
      },
      target: 'Target',
      audit: 'imported, awaiting confirmation',
      why: {
        movie: 'This is a film; it has no season or episode',
        media_by_title: 'The download named no title; recognised {{title}} by its name',
        title_exact: 'The release title is exactly {{title}}',
        title_contained: 'The release name contains {{title}}',
        title_partial: 'The release name carries most of {{title}}',
        year_matches: 'The year {{year}} matches',
        year_differs: 'The release says {{year}}; this title is from {{expected}}',
        title_mismatch: 'The release title {{release_title}} does not look like {{title}}',
        no_media: 'The download named no title, so there are no seasons to check against',
        season_from_job: 'The download names season {{season}}',
        season_from_release: 'The release name says season {{season}}',
        season_from_folder: 'The folder says season {{season}}',
        season_from_arc: 'The release carries the arc {{arc}}, which is season {{season}}',
        final_season: 'The release says final season; the last season is {{season}}',
        single_season: 'Only an episode number, and TMDB has one season',
        absolute_group: 'TMDB’s absolute order puts #{{number}} at {{episode}}',
        absolute_cumulative: 'Counting seasons in order puts #{{number}} at {{episode}}',
        cour_offset:
          'Part {{part}} of season {{season}} starts at episode {{first}}, so its episode {{number}} is {{episode}}',
        air_date_run:
          'TMDB has no season {{season}}; air dates split it into {{runs}} runs, and run {{season}} starts at {{episode}}',
        episode_not_on_tmdb: 'TMDB has no episode {{number}} in season {{season}}',
        absolute_within_first_season:
          '#{{number}} does not go past the {{episodes}} episodes of season {{season}}; it could be episode {{number}} of a later season that counts from 01 again',
        air_date_unknown:
          'The release says it aired on {{aired}}, but TMDB has no air date for {{episode}}',
        air_date_mismatch:
          'The release says it aired on {{aired}}; TMDB says {{episode}} aired on {{tmdb_aired}}',
        range_spans_seasons:
          'The release covers {{start}}–{{end}}, which does not fit in one season',
        specials_numbering: 'Release groups number specials differently from TMDB’s season 0',
        classified: 'Classified as {{kind}}; nothing to decide',
        disc_structure: 'A disc structure; Berth does not unpack those',
        own_numbered_special:
          'A special the release numbers itself; TMDB numbers its specials differently',
        no_episode: 'No season and episode could be worked out',
        subtitle_orphan: 'No video in this download goes with this subtitle',
        subtitle_same_name: 'The subtitle and the video share a name',
        subtitle_folder_episode:
          'The subtitle sits in a subtitle folder and names episode {{number}}',
        subtitle_follows: 'It goes with {{video}}',
        video_not_imported: 'Its video is “{{action}}”, so the subtitle follows',
        target_contested: 'Another file in this download would be written to {{target}}',
        span_clash:
          'Another episode file here starts at the same episode but covers a different range; Jellyfin 12 groups by season and episode only, so it would fold them into one and the later episodes would disappear',
        library_span_clash:
          'The library already has {{known}}, which starts at the same episode but covers a different range; Jellyfin 12 would fold them into one and the later episodes would disappear',
        too_many_files:
          'This download maps {{files}} files into season {{season}}, which TMDB says has {{episodes}} episodes',
        strategy_outlier: 'The rest of this download was read by {{strategy}}; this file was not',
        season_complete: 'This download covers season {{season}} end to end',
        medium_held_by_route: 'This library route does not import medium confidence by itself',
        set_by_user: 'An administrator set this row',
        same_version: 'The library already has {{known}}: the same episode with the same tags',
      },
      strategy: {
        explicit: 'the name itself',
        folder: 'the folder',
        context: 'the download',
        arc_name: 'the arc name',
        single_season: 'the single season',
        absolute_group: 'TMDB’s absolute order',
        absolute_cumulative: 'counting seasons',
        air_date_offset: 'air dates',
        cour_offset: 'the part number',
        movie: 'film',
      },
      kind: {
        video: 'video',
        subtitle: 'subtitle',
        font: 'font',
        audio: 'audio',
        image: 'image',
        archive: 'archive',
        sample: 'sample',
        disc: 'disc structure',
        extra: 'extra',
        other: 'other',
      },
      replan: 'Plan it again',
      replanning: 'Planning…',
      replanOff:
        'The replan was not sent. Berth’s own API did not answer — check that it is still running.',
      replanned: 'Planned again; it is now {{state}}.',
    },
    refusal: {
      media_missing: 'Berth does not hold this title. Open its detail page again.',
      route_missing: 'That library route is gone. Pick another one.',
      route_kind_mismatch:
        'That library route cannot hold this kind — shows only go to a tvshows library, films only to a movies one.',
      route_disabled:
        'That library route is disabled. Turn it back on in settings, or pick another one.',
      route_unhealthy:
        'That library route is red right now, so nothing sent to it would reach the library. The health page says which line came loose.',
      source_unavailable:
        'The indexer would not hand over this torrent. The link may have expired — search again and send the fresh one.',
      job_missing: 'That download is gone.',
      not_retryable:
        'This one cannot be retried — only the ones that failed to send or to import can. Reload to see where it stands now.',
      not_replannable:
        'This one cannot be planned again — the plan it is importing is already being applied to files. Reload to see where it stands now.',
      client_unreachable:
        'qBittorrent could not be reached, so nothing was deleted. Check that it is up, then try again.',
      delete_files_requires_remove_torrent:
        'To delete the downloaded files, remove the torrent from qBittorrent at the same time — otherwise it fetches the whole thing again on its next recheck.',
      not_reimportable:
        'This one cannot be imported again right now — it is still downloading, planning or importing, or it never finished downloading (complete holds only a partial copy). Reload to see where it stands now.',
      content_missing:
        'This download is no longer in complete (or it has no files left), so nothing was touched. Download it again to import it.',
      moved_on:
        'Something else changed this download after you pressed the button (another tab may have just deleted it), so nothing was touched. Reload to see where it stands now.',
      low_disk_space:
        'The download folder has less free space than the threshold, so nothing was sent. Free up some space, or lower the threshold in service settings, then send it again.',
      job_removed:
        'This torrent was downloaded before and then deleted. Its record is still kept, so it will not be downloaded again. Open that download to decide: import it again if complete still holds the files, or delete it together with its record to download it afresh (both need an administrator).',
      review_needs_admin:
        'This one is waiting for review. Planning it again would throw away what an administrator reviewed, so only an administrator can do it.',
    },
    delete: {
      label: 'Delete',
      pending: 'Deleting…',
      confirm: 'Delete',
      title: 'Choose what to delete',
      lede: 'This deletes what this download touched. Other downloads of the same title are left alone.',
      unlink: 'Remove the hard links from the library',
      unlinkHint:
        'Jellyfin drops these files on its next scan. The originals in the download folder stay.',
      removeTorrent: 'Remove the torrent from qBittorrent',
      removeTorrentHint: 'The files stay, but seeding stops.',
      deleteFiles: 'Delete the files in the download folder',
      deleteFilesHint: 'Remove the torrent as well, or qBittorrent fetches the whole thing again.',
      deleteFilesLocked: 'Tick the box above to enable this.',
      purge: 'Clear the ledger and this job’s records',
      purgeHint: 'Leave it off and the job stays on the list as “Deleted”, timeline and all.',
      estimate: {
        pending: 'Measuring each of these files…',
        off: 'Could not work out how much this frees. Berth’s own API did not answer — you can still delete.',
        links_one: '{{count}} link in the library',
        links_other: '{{count}} links in the library',
        sources_one: '{{count}} file in the download folder',
        sources_other: '{{count}} files in the download folder',
        missing_one: '{{count}} more is in the ledger but no longer on disk',
        missing_other: '{{count}} more are in the ledger but no longer on disk',
        frees: 'This frees {{size}}.',
        freesNothing:
          'This frees nothing: the library links and the downloaded files are the same data, so both sides have to go.',
        held: '{{size}} of it is held by a link Berth does not know about, and no choice here gets it back.',
      },
      done: 'Removed {{links}} links, deleted {{sources}} files, freed {{size}}.',
      doneNothing: 'Removed {{links}} links, deleted {{sources}} files. Nothing was freed.',
      kept_one: '{{count}} library file is no longer the one Berth put there and was not deleted.',
      kept_other:
        '{{count}} library files are no longer the ones Berth put there and were not deleted.',
      off: 'The delete did not go out. Berth’s own API did not answer — check that it is up.',
    },
  },
  submit: {
    start: 'Send',
    submit: 'Confirm and send',
    submitting: 'Sending…',
    confirm: 'Once this is sent, the folder for this title in your library will be:',
    needRoute: 'Pick a library route above first. This is the folder name it would get:',
    needRouteError: 'Pick a library route above first.',
    destination: 'Into “{{route}}”',
    willFreeze:
      'The moment a send succeeds this string is fixed; a later TMDB title change will not move it.',
    alreadyFrozen: 'This string is already fixed; this send will not change it.',
    done: 'Sent',
    already: 'Already here',
    toJobs: 'See downloads',
    toRemovedJob: 'See that download',
    off: 'The submission was not sent. Berth’s own API did not answer — check that it is still running.',
  },
  tmdb: {
    problem: {
      credential_missing:
        'Berth has no TMDB credential. It ships without one: get your own key at themoviedb.org and paste it into the setup wizard.',
      credential_rejected:
        'TMDB rejected this credential. It may have been revoked, or lost a few characters on the way in.',
      unreachable:
        'Cannot reach TMDB. Either this machine has no outbound network, or TMDB is down.',
      not_found:
        'TMDB has no such title. It may have been merged or removed — go back to Discover and look it up again.',
      toSetup: 'Open the setup wizard',
      askAdmin: 'Ask an administrator to add the TMDB credential in the setup wizard.',
      retry: 'Retry',
    },
  },
  health: {
    title: 'Health',
    deniedChip: 'Not allowed',
    denied:
      'Only an administrator can change the settings, so you were sent here instead. The health page is read-only diagnostics and everyone can see it.',
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
    failures_one: '{{count}} consecutive failure',
    failures_other: '{{count}} consecutive failures',
    state: {
      ok: 'Ready',
      drift: 'Settings changed',
      failed: 'Blocked',
      unknown: 'Not checked',
      unconfigured: 'Not connected',
    },
    poller: {
      title: 'Download loop',
      lastRound: 'Last poll',
      every: 'every {{seconds}}s while downloading',
      failures: 'Consecutive failures',
      error: 'Last error',
      unknown: {
        title: 'Unclaimed torrents',
        count_one: '{{count}} torrent',
        count_other: '{{count}} torrents',
        help: 'Torrents that carry a Berth category or tag but have no download here. Usually added straight in qBittorrent, or left over from a restored database. Berth leaves them alone.',
      },
    },
    routes: {
      title: 'Routes',
      count_one: '{{count}} route',
      count_other: '{{count}} routes',
      expand: 'Show checks',
      collapse: 'Hide',
      empty:
        'No routes yet. Create them in the last berth of the setup wizard — until then Berth has nowhere to write.',
    },
    fix: {
      title: 'Fix',
      banned:
        'qBittorrent has banned this machine after repeated failed logins. **Changing the password will not help** — it only fails a few more times and restarts the ban. Wait for it to expire (1 hour by default), clear the ban in qBittorrent, or restart its container: the ban lives in memory only. Once the credentials are right, Berth turns green again on its next round.',
      bundled:
        'This service comes from the bundled compose file, so start by checking that its container is still running. The three commands are in triage order: is it there, bring it up, what did it say.',
      existing:
        'This is your own service, and all Berth knows is that it stopped answering. If its address or credentials changed, fill them in again in the setup wizard.',
      unconfigured:
        'This service is not connected yet. Connect it in the setup wizard — until then, whatever it is responsible for simply will not happen.',
      unsupported:
        'Berth needs Jellyfin 12.0 or newer (12.0 is what would have been 10.12). Before upgrading, back up Jellyfin’s /config in full — 12 changes the database and there is no way back — and remove third-party plugins, which cannot load on 12. Run one full library scan afterwards.',
      drift:
        "Berth's recommended settings were changed ({{keys}}). The service itself is still running, but once the download paths or automatic management are wrong, imports will fail sooner or later.",
    },
    toSetup: 'Open the setup wizard',
    toSettings: 'Open service settings',
  },
  settings: {
    title: 'Service settings',
    lede: 'Addresses and credentials are edited in the setup wizard. This page does four things: re-test a connection, set Jellyfin’s public address, set the disk space threshold, and restore recommended settings that were changed.',
    test: 'Test connection',
    testing: 'Testing…',
    testFailed:
      'The test did not go through. The Berth backend may be down — check the container, then try again.',
    editHint: 'Change address or credentials',
    tabs: {
      label: 'Settings',
      services: 'Services',
      routes: 'Routes',
    },
    jellyfin: {
      title: 'Jellyfin public address',
      lede: 'The address behind “Open in Jellyfin” on the library page — not the one Berth itself connects to. Fill it in only when Jellyfin sits behind a reverse proxy or on another domain.',
      label: 'Public address',
      placeholder: 'https://jellyfin.example.com',
      derivedHost: 'Not set: links open on this browser’s current host name, port {{port}}.',
      derivedUrl: 'Not set: links open at {{url}}.',
      set: 'Links open at {{url}}.',
      unknown: 'Not set, and Berth cannot work out where Jellyfin lives — please fill it in.',
      save: 'Save',
      saving: 'Saving…',
      saved: 'Saved.',
      invalid: 'This needs to be an address starting with http:// or https://.',
      failed: 'It was not saved. Berth’s own API did not answer — check that it is still running.',
    },
    disk: {
      title: 'Disk space threshold',
      lede: 'When the disk holding incomplete or complete has less free space than this, an issue opens; it closes on its own once there is room again. Berth imports with hard links, which take no space — downloads do — so the unit is GB.',
      label: 'Keep at least (GB)',
      hint: '0 turns the check off.',
      save: 'Save threshold',
      saving: 'Saving…',
      saved: 'Saved, and measured again right away.',
      invalid: 'It has to be a whole number, 0 or more.',
      failed: 'It was not saved. Berth’s own API did not answer — check that it is still running.',
    },
    drift: {
      title: 'qBittorrent recommended settings',
      clean: 'All five recommended keys still hold their recommended values.',
      changed_one: '{{count}} key differs from the recommended value.',
      changed_other: '{{count}} keys differ from the recommended values.',
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
  routeSettings: {
    title: 'Routes',
    lede: 'Each route is one Jellyfin library plus one write target, and a library can have several — one per disk, say. A disabled route takes no new downloads; a route that downloads or imported files still point at cannot be deleted.',
    empty:
      'No routes yet. Create them in the last berth of the setup wizard, so Berth has somewhere to write.',
    disabled: 'Disabled',
    manage: 'Manage',
    collapse: 'Collapse',
    link: 'Go to route settings',
    usage: {
      jobs_one: '{{count}} download',
      jobs_other: '{{count}} downloads',
      files_one: '{{count}} imported file',
      files_other: '{{count}} imported files',
    },
    edit: {
      name: 'Name',
      enabled: 'Enabled',
      enabledHint:
        'A disabled route takes no new downloads; the ones already on their way still import. Enabling it runs the five checks again first.',
      identity:
        'The slug and the write target cannot change once the route exists: the category, the complete subdirectory and the ledger all go by them. To use another target, add a route and delete this one.',
      save: 'Save',
      saveRechecks:
        'Saving runs the five checks below again: that round creates the qBittorrent category and writes a probe file into the write target.',
      saving: 'Saving and checking…',
      saved: 'Saved.',
      unhealthy:
        'Not all five checks passed, so this route stays disabled. Fix the red one below and press Save again.',
      failed:
        'It was not saved. The Berth backend may be down — check the container and press again.',
      nameRequired:
        'The name cannot be blank: the library page’s route bar and the route picker when sending a download both show it.',
    },
    recheck: 'Check again',
    rechecking: 'Checking…',
    recheckFailed:
      'The check did not finish. The Berth backend may be down — check the container and press again.',
    rechecked: 'The check finished.',
    delete: {
      label: 'Delete this route',
      confirm: 'Delete it',
      pending: 'Deleting…',
      warning:
        'Deleting removes this route from Berth. The qBittorrent category and the complete subdirectory stay where they are; rebuilding a route with the same name picks them up again.',
      inUse:
        '{{jobs}} and {{files}} point at this route, so it cannot be deleted. Disable it instead and new downloads will no longer pick it; the ones already on their way still import.',
      inUseDisabled:
        '{{jobs}} and {{files}} point at this route, so it cannot be deleted. It is disabled, so new downloads will not pick it.',
      refused:
        'When it came to deleting, {{jobs}} and {{files}} turned out to point at this route, so it cannot be deleted. Disable it instead and new downloads will no longer pick it.',
      refusedUncounted:
        'Downloads or imported files turned out to point at this route when it was deleted, so it cannot be deleted. Disable it instead and new downloads will no longer pick it.',
      failed:
        'It was not deleted. The Berth backend may be down — check the container and press again.',
      done: 'Deleted “{{name}}”.',
    },
    disable: {
      label: 'Disable this route',
      pending: 'Disabling…',
      done: 'Disabled “{{name}}”: new downloads will no longer pick it.',
      failed:
        'It was not disabled. The Berth backend may be down — check the container and press again.',
    },
    add: {
      open: 'Add a route',
      title: 'Add a route',
      lede: 'One Jellyfin library can have several routes, each writing to a path of its own. Jellyfin reports the paths, so you pick one here; if Jellyfin does not have the path yet, add it to the library in Jellyfin first.',
      loading: 'Asking Jellyfin for its libraries…',
      library: 'Library',
      target: 'Write target',
      taken: 'Already “{{name}}”',
      noneFree:
        'Every path this library reports already has a route. Add another path to it in Jellyfin, then come back.',
      openJellyfin: 'Add a path in Jellyfin',
      pickFirst: 'Pick a library and a write target that has no route yet.',
      submit: 'Create and check',
      submitting: 'Creating and checking…',
      createdOk: 'Created “{{name}}”: all five checks passed and it is enabled.',
      createdRed:
        'Created “{{name}}”, but not all five checks passed, so it stays disabled. Fix the mount, check it again in its row, then tick Enabled.',
      unreachable:
        'Could not get the library list from Jellyfin, and a new route needs the paths it reports. Raw message:',
      failed:
        'It was not created. The Berth backend may be down — check the container and press again.',
      refusal: {
        library_missing:
          'Jellyfin no longer has this library. Cancel and open this section again to ask for the list afresh.',
        library_unsupported: 'Berth writes into movie and TV libraries only.',
        target_not_in_library:
          'This path no longer belongs to the library — it just changed in Jellyfin. Cancel, reopen this section and pick again.',
        target_taken:
          'Another route just took this path. Each route needs a write target of its own.',
        route_conflict:
          'Another route was being created at the same moment, so this one was not saved. Press Create and check again.',
        jellyfin_unreachable:
          'Jellyfin did not answer when the route was being created. Check that it is running and press again.',
      },
    },
  },
  common: {
    expand: 'Expand',
    collapse: 'Collapse',
    collapseNamed: 'Collapse {{name}}',
    audits_one: '{{count}} to check',
    audits_other: '{{count}} to check',
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

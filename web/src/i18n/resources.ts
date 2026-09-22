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
    // 16:9 的那一塊：這裡沒有海報可說。
    noArt: '無圖',
    down: '問不到 Jellyfin，繼續觀看與下一集暫時看不到。',
    retry: '重試',
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
    // 排序與類型、年份篩選（票 06）。選項照 jellyfin-web 的排序選單，兩種媒體庫各開哪幾個由後端說。
    sort: {
      label: '排序',
      order: '排序方向',
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
      },
      clearBoth: '清除類型與年份',
    },
    showing_one: '顯示 {{count}} 部作品',
    showing_other: '顯示 {{count}} 部作品',
    // Berth 經手、Jellyfin 還沒有的作品。不叫「在路上」：失敗的、Jellyfin 找不到的也在這裡。
    notInJellyfin: '還沒進 Jellyfin',
    notInJellyfinCount_one: '{{count}} 部作品還沒進 Jellyfin',
    notInJellyfinCount_other: '{{count}} 部作品還沒進 Jellyfin',
    pages: '分頁',
    previous: '上一頁',
    next: '下一頁',
    // 看得見的是「1–100 / 523」，聽得見的是這一句。
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
      review: '這個媒體庫沒有待審的作品。',
      unmatched: '這個媒體庫沒有對不到檔案的作品。',
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
        note: '解析器對不到任何一集，所以這些檔案留在 complete 原位，不入庫。',
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
      linked: '已鏈接',
      link_failed: '鏈接失敗',
      jellyfin_scan_requested: '已通知 Jellyfin',
      jellyfin_item_resolved: 'Jellyfin 已收錄',
      jellyfin_request_failed: 'Jellyfin 請求沒成',
    },
    timeline: {
      loading: '讀取時間線…',
      empty: '這一筆還沒有任何事件。',
      off: '讀不到時間線。',
      retried: '狀態退回「已建立」，接著再送一次。',
      retriedImport: '狀態退回「入庫中」，從還沒鏈接的檔案接著做。',
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
      },
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
          '有檔案的季集推不出來，或這一包的數量與 TMDB 對不上。M1 還沒有審核佇列——改好 Route 或等 TMDB 補上季集之後按「重新規劃」。',
        medium_not_allowed:
          '這條 Route 不讓 medium 信心的檔案自動入庫，所以整份計劃停下來等人看。逐檔確認要等審核佇列；現在能做的是看過下面每一列的理由。',
        nothing_to_import: '這一包裡沒有任何一個檔案會進媒體庫。多半是送錯了 torrent。',
        target_exists:
          '媒體庫裡這個位置已經有一個不是 Berth 鏈接的檔案，Berth 不會覆寫它；其餘檔案已經入庫了。M1 還沒有審核佇列——把那個檔案移走之後按「重新規劃」。',
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
    lede: '位址與憑證在設定精靈改。這一頁做三件事：重測連線、把被改掉的建議設定還原，以及 Jellyfin 的對外網址。',
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
    build_one: 'Build {{count}} route and check',
    build_other: 'Build {{count}} routes and check',
    recheck_one: 'Check {{count}} route again',
    recheck_other: 'Check {{count}} routes again',
    requestFailed:
      'The request did not finish. The Berth backend may be down — check the container and press again.',
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
        'Already has a route: the wizard only adds, it never changes or deletes one. If it was a mistake, use the delete under that route below; once setup is done, manage routes under Settings → Library paths.',
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
  },
  watching: {
    resume: 'Continue watching',
    nextUp: 'Next up',
    count_one: '{{count}} item',
    count_other: '{{count}} items',
    showAll_one: 'Show all {{count}}',
    showAll_other: 'Show all {{count}}',
    showFewer: 'Show fewer',
    noArt: 'NO ART',
    down: "Berth can't reach Jellyfin, so Continue watching and Next up are unavailable for now.",
    retry: 'Retry',
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
    sort: {
      label: 'Sort',
      order: 'Sort order',
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
      },
      clearBoth: 'Clear genres and years',
    },
    showing_one: 'Showing {{count}} title',
    showing_other: 'Showing {{count}} titles',
    notInJellyfin: 'Not in Jellyfin yet',
    notInJellyfinCount_one: '{{count}} title not in Jellyfin yet',
    notInJellyfinCount_other: '{{count}} titles not in Jellyfin yet',
    pages: 'Pages',
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
      review: 'Nothing in this library is waiting for review.',
      unmatched: 'Nothing in this library has unmatched files.',
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
        note: 'The parser could not tie these to any episode, so they stay where they are in complete and are not imported.',
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
      linked: 'Linked',
      link_failed: 'Link failed',
      jellyfin_scan_requested: 'Jellyfin told',
      jellyfin_item_resolved: 'In Jellyfin',
      jellyfin_request_failed: 'Jellyfin request failed',
    },
    timeline: {
      loading: 'Reading the timeline…',
      empty: 'Nothing has happened to this job yet.',
      off: 'Could not read the timeline.',
      retried: 'Back to created, then sent again.',
      retriedImport: 'Back to importing; it picks up from the files not linked yet.',
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
      },
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
          'Some files could not be placed in a season and episode, or the count does not match TMDB. There is no review queue yet in M1 — fix the route or wait for TMDB, then press replan.',
        medium_not_allowed:
          'This library route does not auto-import medium-confidence files, so the whole plan stopped for a person to look at. Confirming file by file comes with the review queue; for now, read the reason on each row below.',
        nothing_to_import:
          'Nothing in this torrent would reach the library. Most likely the wrong torrent was sent.',
        target_exists:
          'A file Berth did not link already sits at this spot in the library, and Berth will not overwrite it; the other files are already in. There is no review queue yet in M1 — move that file away, then press replan.',
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
      title: 'Library paths',
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
    lede: 'Addresses and credentials are edited in the setup wizard. This page does three things: re-test a connection, restore recommended settings that were changed, and set Jellyfin’s public address.',
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
    title: 'Library paths',
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

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
    library: '媒體庫路徑',
    indexers: 'Prowlarr',
    tmdb: 'TMDB',
    indexerNone: '尚未加入索引站',
    indexerCount_one: '{{count}} 個索引站',
    indexerCount_other: '{{count}} 個索引站',
    routeCount_one: '{{count}} 條 Route',
    routeCount_other: '{{count}} 條 Route',
    unassigned: '未指派',
    waiting: '待靠泊',
    // 手機寬度的那一列摘要（M4 票 30）。
    summary: {
      expand: '展開',
      collapse: '收起',
      blocked: '阻擋',
    },
  },
  setup: {
    title: '設定精靈',
    stage: {
      berth: '泊位 {{code}}',
      final: '收尾',
    },
    step: '第 {{current}} 個，共 {{total}} 個泊位',
    resumed: '進度已保留，關掉瀏覽器再回來會回到這一步。',
    statusFailed: '讀不到精靈的狀態。',
    notAdministrator:
      '精靈只有 Jellyfin 管理員能繼續：{{name}} 登得進 Jellyfin，但不是這台的管理員。登出，改用管理員登入。',
    nav: {
      label: '泊位導覽',
      previous: '上一個泊位',
      next: '前往下一個泊位',
      missing: '還差',
    },
    stray: {
      where: '回頭看：{{place}}',
      current: '目前走到：{{place}}',
      back: '回到目前這一步',
    },
    revisit: {
      label: '回頭看',
      can: '這裡能做',
      elsewhere: '不在這裡做',
      jellyfin: {
        can: '看擁有者是誰。擁有者成立之後來源鎖住；既有的那一台換了位址（例如改了 port）按測試結果上的「改位址」，只收同一台伺服器。',
        bundledCan:
          '看擁有者是誰。擁有者成立之後來源鎖住；套件內的那一台位址由 compose 決定，不用改。',
        elsewhere: '擁有者的密碼在 Jellyfin 裡改。換成另一台 Jellyfin 等於換擁有者，Berth 不支援。',
      },
      qbittorrent: {
        can: '改選套件內或既有（這一頁要重做）、改既有那一台的位址或憑證、更換套件內那一台的 WebUI 登入。一個全域偏好都不寫。',
        elsewhere:
          '全域偏好（預設儲存路徑、自動管理…）都在 qBittorrent 自己的介面上改，Berth 不寫也不看——它的下載只走自己的 berth-* 分類。',
      },
      routes: {
        can: '精靈只新增：套件內可以在清單上加還沒建的媒體庫；補上新勾的媒體庫，並重驗每一條 Route 的每一條纜繩。選錯的那一條在它底下刪掉。',
        elsewhere: 'Route 的改名與停用在精靈跑完之後的「設定 → 媒體庫路徑」。',
      },
      indexer: {
        bundled: {
          can: '改選套件內或既有、測試並加更多公開站、試搜、移除不要的站、更換介面登入。加過的站不會被加第二次。',
          elsewhere: '要帳號的站（私站、半私站）在 Prowlarr 自己的介面上加。',
        },
        existing: {
          can: '改選套件內或既有、重新讀取站的清單、試搜；接的是 Prowlarr 時，也可以測試公開站、按一次加進它。加過的站不會被加第二次。',
          elsewhere:
            '移除站、加要帳號的站、改介面登入，都在你那一台自己的介面上做；Berth 不移除你的站，也不碰它的登入。',
        },
      },
      tmdb: {
        can: '重貼一把 key 再測一次；測不過的 key 照樣存下來，改一個字再按就好。',
        elsewhere: 'key 本身的申請、撤銷與重發在 themoviedb.org 的「設定 → API」。',
      },
    },
  },
  owner: {
    title: {
      choose: '先選 Jellyfin 是哪一台',
      create: '建立 Jellyfin 管理員',
      signIn: '用你的 Jellyfin 管理員登入',
      owned: '擁有者：{{name}}',
    },
    lede: {
      choose:
        'Berth 沒有自己的帳號，登入一律交給 Jellyfin。所以第一件事是說出用哪一台：compose 帶來的那一台，或你自己已經在跑的那一台。選了 Berth 才去連它。',
      create:
        'Berth 沒有自己的帳號：這一組就是之後登入 Berth 用的 Jellyfin 帳號。Berth 會以它建立 Jellyfin 的管理員，你就是 Berth 的擁有者；其他人用自己的 Jellyfin 帳號登入，角色由 Jellyfin 決定。',
      signIn:
        'Berth 沒有自己的帳號，登入一律交給 Jellyfin。用這台 Jellyfin 的管理員登入，你就是 Berth 的擁有者；其他人用自己的 Jellyfin 帳號登入，角色由 Jellyfin 決定。',
      owned:
        '{{name}} 是這台 Jellyfin 的管理員，也是 Berth 的擁有者。之後登入 Berth 就用這個 Jellyfin 帳號；密碼在 Jellyfin 裡改。',
    },
    cutaway: {
      title: '將會做什麼',
      create: '建立',
      finish: '完成',
      change: '改動',
      owner: '擁有者',
      form: '建立或登入',
      depends: '連上之後看那一台：已經有管理員就登入，還沒有就建立',
      stored: '不存下',
      admin: 'Jellyfin 管理員',
      startup: 'Jellyfin 的初始設定',
      apiKey: 'API key「Berth」',
      nothing: '不改這台 Jellyfin 的任何設定',
      password: '你的密碼（只交給 Jellyfin）',
      passwordCarried: '你的密碼（交給 Jellyfin；套件內 qBittorrent 與 Prowlarr 的介面也設成它）',
    },
    carry: {
      label: '套件內 qBittorrent 與 Prowlarr 的介面也用這組',
      hint: '到那兩頁自動帶入，不用再打一次密碼；Berth 照樣先向 Jellyfin 驗過才寫。密碼只留在這個分頁的記憶體裡，不存進 Berth、也不寫進瀏覽器——重新整理之後會再問一次。',
    },
    field: {
      username: 'Jellyfin 帳號',
      password: '密碼',
      confirm: '再輸入一次密碼',
    },
    submit: {
      create: '建立管理員並登入',
      signIn: '登入',
    },
    submitting: {
      create: '建立中…',
      signIn: '登入中…',
    },
    refused: {
      jellyfin_unresolved: 'Jellyfin 還沒連上。先讓上面那一條測試通過，再登入。',
      invalid_credentials: 'Jellyfin 不認這組帳號或密碼。',
      not_administrator:
        '這個帳號登得進 Jellyfin，但不是管理員。擁有者要改得動設定——用這台 Jellyfin 的管理員登入。',
      jellyfin_failed:
        'Jellyfin 那一段沒做完：技術細節裡是那一步的錯誤訊息。排除之後再按一次，做過的不會重做。',
      owner_exists:
        '擁有者已經成立了，這裡不換人。Berth 的 API key 要換的話，到「設定 → Jellyfin」用管理員重新登入。',
      target_changed:
        'Jellyfin 的位址在你填表時被換過，帳密沒有送出去。重新測試，確認上面的位址是你要的那一台，再送一次。',
    },
    saved: '擁有者 · {{name}}',
    locked:
      '擁有者是這一台 Jellyfin 上的帳號，換一台等於換擁有者，所以來源鎖住了。同一台換了位址可以改，另一台伺服器會被擋下。',
    startup: {
      language: '語言與地區',
      languageHint:
        '寫進這台 Jellyfin 自己的初始設定：它的介面語言，以及抓 metadata 用的語言與國家。之後在 Jellyfin 的控制台改。',
      remote: '開啟遠端存取',
      remoteHint:
        '讓區網以外的裝置連得進這台 Jellyfin。Berth 從同一台主機的容器連進來，用不到它，所以預設不開。',
    },
    reSignIn: {
      title: 'Berth 的 API key 要換一把',
      lede: '這台 Jellyfin 不收 Berth 存的那一把了（多半是在 Jellyfin 的「API 金鑰」被刪了）。用它的管理員重新登入，Berth 換一把新的，再測一次。',
    },
    error: {
      blank: '帳號與密碼都要填。',
      mismatch: '兩次輸入的密碼不一樣。',
      passwordSpaces: 'Jellyfin 不收只有空白的密碼。',
      noPassword:
        'Berth 不收沒有密碼的 Jellyfin 帳號當擁有者：擁有者能改 Berth 的所有設定，沒有密碼等於誰都能。先在 Jellyfin 的「控制台 → 使用者」替這個帳號設一組密碼，再回來登入。',
      username:
        "Jellyfin 的帳號只能用文字、數字、空格與 - _ ' . @ + 這幾個符號，也不能只是「.」或「..」。",
    },
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
  },
  choice: {
    legend: '這一台 {{service}} 是哪一台？',
    bundled: {
      title: '套件內',
      lede: 'compose 帶來的那一台 {{service}}。Berth 連它、替你設定好：',
      // 主機名解不到（M4 票 30）：只查過 DNS，還沒連它。停掉的容器與不在 COMPOSE_PROFILES 裡的服務一樣解不到，
      // 分不出是哪一種，所以說「沒在跑」、補法兩種都給（票 35）。
      absent: '這套 compose 的 {{service}} 沒在跑。',
      absentFix:
        '要用套件內的 {{service}}：照它沒在跑的原因做下面其中一種，然後點「套件內」。要接你自己的那一台就選「既有」。',
    },
    bringBack: {
      stopped: '容器停了：',
      missing: '{{kind}} 不在 COMPOSE_PROFILES 裡：',
    },
    existing: {
      title: '既有',
      lede: '你自己已經在跑的那一台 {{service}}。Berth 不改你原本的設定，{{adds}}',
      // 「只連它」不對（M4 票 31）：Route 檢查前 Jellyfin 的路徑已經加上、未初始化的那一台會被跑初始精靈。
      // 照實說會加什麼、什麼時候加。
      adds: {
        jellyfin:
          '只在頁 3 你按下時替媒體庫多加一條 Berth 寫入用的路徑（原本的路徑不動）。它還沒跑過自己的初始精靈的話，頁 1 會用你填的帳密替它跑完。',
        qbittorrent:
          '只在頁 3 你按下時建 berth- 開頭的分類；檢查時暫時加一個停住的探測 torrent、隨即移除。偏好一個鍵都不寫。',
        prowlarr: '只加你在頁 4 勾起來的站；原本的站不動。',
      },
      sameHost:
        '條件：它與 Berth 在同一台主機，而且把 Berth 的 DATA_ROOT 也掛在容器路徑 /data——只能是 /data，Berth 的下載與媒體庫目錄固定在它底下。原本的掛載不用動，多加這一條就好。DATA_ROOT 要在建得了硬鏈接的檔案系統上（exFAT、網路磁碟、mergerfs 不行）；另一台 NAS 上的接不上。',
      library:
        '它要先有對應類型的媒體庫（電影、劇集）：Berth 不替你的 Jellyfin 建媒體庫，只在頁 3 替勾選的媒體庫加一條路徑。',
      profiles:
        '選了既有，套件內那一台用不到了：把 .env 的 COMPOSE_PROFILES 換成第一行（{{kind}} 不在裡面），再用第二行停掉已經在跑的那一台——只改 COMPOSE_PROFILES 再 docker compose up -d 停不掉它。忘了也不致命。',
      floor: {
        jellyfin: '版本下限：Jellyfin 12.0。從 10.x 升級是單向的，先看升級注意。',
        qbittorrent: '版本下限：qBittorrent 4.4（Web API 2.8.4）。',
        prowlarr: '版本下限：Prowlarr 1.3.2。',
      },
      upgradeNotes: 'Jellyfin 12.0 升級注意',
    },
    switchToBundled: '改用套件內的那一台',
    saveFailed: '沒有存下這個選擇。',
    refused: {
      jellyfin_owned: '擁有者成立之後，Jellyfin 的來源換不了。',
      other_server:
        '沒有存：這個位址上回答的是另一台 Jellyfin，不是擁有者所在的那一台。擁有者、Berth 的 API key 與媒體庫都在原本那一台；換一台等於換擁有者，Berth 不支援。',
      unverified:
        '沒有存：這個位址沒有說出它是哪一台 Jellyfin（{{detail}}），認不出是不是同一台。確認位址與 port 再試一次。',
    },
    useBundled: '使用套件內的 {{service}}',
    useBundledLede:
      '按下之後 Berth 存下這個選擇，連 compose 帶來的那一台 {{service}} 測一次（只讀）。',
    switchAway: {
      jellyfin: '換一台 Jellyfin：這一頁要重做。',
      qbittorrent:
        '換一台 qBittorrent：Berth 沒改過你那一台的偏好；這一頁要重做，媒體庫與路徑也要重新檢查——分類要建在新的那一台上。',
      prowlarr: '換一台 Prowlarr：這一頁要重做。',
    },
    switchWarning: {
      qbittorrent:
        '換一台 qBittorrent：這一頁要重做，媒體庫與路徑也要重新檢查——分類要建在新的那一台上。',
      prowlarr: '換一台 Prowlarr：這一頁要重做。',
    },
    leftovers: {
      reading: '讀取 Berth 在原本那一台建了什麼…',
      readFailed: '讀不到 Berth 在原本那一台建了什麼。',
      heading: 'Berth 在原本那一台建的，換了之後留在那裡：',
      remembered: '連不到原本那一台。以下是 Berth 記得在那裡建過的，沒辦法確認現在還在不在：',
      none: '原本那一台上沒有 Berth 建的東西。',
      noneRemembered: '連不到原本那一台；Berth 不記得在那裡建過東西。',
      category: '分類',
      empty: '空的',
      torrents_one: '{{count}} 個 torrent',
      torrents_other: '{{count}} 個 torrent',
      sites: '加入的站',
      separator: '、',
      login: 'Berth 設的介面登入',
      removeEmpty_one: '移除 {{count}} 個空的 berth- 分類',
      removeEmpty_other: '移除 {{count}} 個空的 berth- 分類',
      removed: '空的 berth- 分類已移除。',
      removeFailed: '沒有移除。',
    },
  },
  connection: {
    state: {
      ok: '連上了',
      waiting: '啟動中',
      failed: '沒通過',
      timeout: '逾時',
    },
    testing: '測試中',
    untested: '還沒測',
    result: '測試結果',
    waitingLabel: '等待中',
    waiting: '{{waited}} / {{window}} 秒',
    waitingHint: '容器還在啟動。Berth 每 3 秒再測一次，到上限為止。',
    retest: '重新測試',
    retesting: '測試中…',
    announce: '{{service}} {{state}}：{{reason}}',
    edit: '改位址或憑證',
    editAddress: '改位址',
    pasteKey: '用這把 key 再測一次',
    fix: {
      notDeployed:
        '這個主機名解不到，{{kind}} 的容器沒在跑：可能停掉了（停掉的容器不在 compose 的網路上），或不在 .env 的 COMPOSE_PROFILES 裡。照原因做下面其中一種，或改選「既有」接你自己的那一台。起來之後按「重新測試」。',
      somethingElse:
        '等到上限了，{{kind}} 這個主機名上回應的還是別的東西。確認 compose 裡那個服務名對應的是它，或改選「既有」。',
      apiKeyMissing:
        '唯讀掛載與環境變數都讀不到 Prowlarr 的 API key。到 Prowlarr 的「設定 → 一般 → 安全性」抄下來貼在下面，仍然是套件內。',
      apiKeyEmpty:
        '你自己的 Prowlarr 要一把 API key 才連得上：在它的「設定 → 一般 → 安全性」複製，貼進上面的欄位再測一次。',
      prowlarrMount:
        'Berth 讀到的 API key 不被接受。Berth 每次測試都重讀唯讀掛載 /ext/prowlarr 裡的 config.xml，在 Prowlarr 重新產生 key 也跟得上：確認 berth 的 compose 有把 ${CONFIG_ROOT}/prowlarr 掛進去，再按「重新測試」。',
      whitelist:
        '套件內那一台要帳密：Berth 的免密白名單沒生效。重啟它讓預置腳本補上白名單，再重新測試：',
      bundledDown: '容器還沒起來。在宿主上確認它活著、看它的 log：',
      dataUnseen:
        '你的 qBittorrent 看不到 {{root}}：Berth 在那裡寫了一個檔，它校驗之後說一點都沒有——它多半沒掛 {{root}}（例如只掛了 /downloads），下載會寫進 Berth 拿不到的地方。在你原本那一份 compose（或 docker run 指令）的 qBittorrent 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 {{root}}（${DATA_ROOT} 換成那個值；容器路徑只能是 {{root}}）。原本的掛載不用動：/downloads 留著，舊 torrent 照常做種，Berth 只在 {{root}} 底下讀寫。Berth 不做 remote path mapping。重建它（docker compose up -d，或刪掉容器再照新的指令 docker run）之後重新測試：',
      dataUnseenBundled:
        '這套 compose 的 qbittorrent 看不到 {{root}}：Berth 在那裡寫了一個檔，它校驗之後說一點都沒有。compose 裡它的這一條掛載被改掉了；改回來、跑 docker compose up -d qbittorrent 之後重新測試：',
      dataUnreadable:
        'qBittorrent 容器裡的使用者讀不了 {{root}} 底下 Berth 寫的檔：讓它與 berth 用同一組 PUID / PGID，或放寬那個目錄的權限，再重新測試。',
      dataUnsettled: '等 qBittorrent 手上的校驗跑完，再重新測試。',
      credentials: '帳號或密碼不對。改好上面的欄位再測一次。',
      authWarning:
        'Berth 這邊已經數到連續 {{failures}} 次登入失敗。qBittorrent 預設連錯 {{limit}} 次就封鎖 Berth 這台的 IP {{minutes}} 分鐘；最多再錯 {{left}} 次就會被封。',
      authWarningLast:
        'Berth 這邊已經數到連續 {{failures}} 次登入失敗，qBittorrent 預設這時已經封鎖 Berth 這台的 IP {{minutes}} 分鐘。先把帳密改對，等封鎖過期或重啟 qBittorrent 再測。',
      prowlarrKey:
        'API key 不對：在 Prowlarr 的「設定 → 一般」複製 API key（不是介面登入的密碼），貼上再測一次。',
      banned:
        'qBittorrent 預設連錯 {{limit}} 次就封鎖這個 IP {{minutes}} 分鐘，被封的時候連對的帳密也會被拒。被封的是 qBittorrent 看到的來源 IP：Berth 經宿主的 port 或 host.docker.internal 連它時，那多半也是你瀏覽器的來源，所以這段時間你從宿主開它的 WebUI 也登不進去。等 {{minutes}} 分鐘，或重啟 qBittorrent（封鎖只記在它的記憶體裡）；先把帳密改對，解封之後只測一次。',
      address: '連不到這個位址。確認 port 沒填錯、服務在跑，而且 Berth 的容器連得到那台主機。',
      schemeMismatch:
        '這個 port 講的是 http，不是 https：把位址開頭的 https:// 改成 http://，再測一次。',
      schemeMissing:
        '位址要以 http:// 或 https:// 開頭，例如 http://192.168.1.10:8080。Berth 不替你猜是哪一種。',
      outdated: '至少要 {{floor}}，這一台是 {{version}}；等也不會好。升級之後再測一次。',
      outdatedBundled:
        '至少要 {{floor}}，套件內那一台是 {{version}}：拉新的 image 再起一次，然後重新測試。',
      jellyfinKey:
        'Berth 存的 API key 這一台不收了（多半是在 Jellyfin 的「API 金鑰」被刪了）。用它的管理員在下面重新登入，換一把新的。',
      otherServer:
        '這個位址上現在回答的是另一台 Jellyfin。擁有者、Berth 的 API key 與媒體庫都在原本那一台：把位址改回它，或確認那個 port 沒被別的容器佔走。',
    },
  },
  reason: {
    connected: '連線測試通過',
    setup_pending: '還沒跑過自己的初始精靈',
    setup_completed: '已經有管理員',
    auth_required: 'API key 不被接受',
    auth_required_login: '帳密不被接受',
    ip_banned: '把 Berth 這台的 IP 封了（連續登入失敗）',
    api_key_missing: '讀不到 API key',
    not_deployed: '找不到這個名字的主機',
    unreachable: '找得到這台主機，但它沒有回應',
    starting: '連得上，但它說自己還在啟動',
    coming_up: '還在起來，還沒正常回應',
    protocol_mismatch: '連得上，但回的東西不是這個服務',
    scheme_mismatch: '連得上，但這個 port 講的是 http，不是 https',
    scheme_missing: '位址沒寫 http:// 或 https://',
    version_unsupported: '連得上，但版本比 Berth 支援的下限舊',
    other_server: '回答的是另一台 Jellyfin，不是擁有者所在的那一台',
    data_unseen: '連得上，但它看不到 Berth 放在 /data 的檔案',
    data_unreadable: '連得上，找得到 Berth 放在 /data 的檔案，但讀不了',
    data_unsettled: '連得上，但它手上的校驗還沒輪到 Berth 的探測檔',
  },
  detail: {
    version: '版本',
    server: '伺服器',
    indexers: '索引站',
    tmdb: 'TMDB',
    credential: '憑證',
    verified: '已驗證',
    unverified: '待驗證',
    absent: '還沒填',
  },
  technical: {
    title: '技術細節',
  },
  request: {
    offline: 'Berth 的後端沒有回應：它可能沒在跑，或網路斷了。確認容器狀態後再試一次。',
    invalid: 'Berth 不收這一次送出的內容，多半是這個畫面過時了。重新整理頁面再試一次。',
    conflict: '這一次與 Berth 現在的狀態衝突（可能另一個分頁剛改過）。重新整理頁面再試一次。',
    server: 'Berth 的後端出錯了。再試一次；還是不行的話看 berth 容器的 log。',
    signedOut: '登入已失效：重新登入 Berth，再試一次。',
    ownerElsewhere:
      '擁有者已經在別處成立了：另一個瀏覽器或分頁先完成了這一步。用那個 Jellyfin 管理員登入，從目前的進度繼續。',
    notAdministrator: '只有 Jellyfin 管理員做得了這件事：你登入的帳號不是這台 Jellyfin 的管理員。',
    signIn: '前往登入',
  },
  failure: {
    not_deployed: '{{service}} 的主機名解不到：它的容器沒在跑、不在這套 compose 裡，或位址打錯了。',
    unreachable: '連不到 {{service}}：它沒在跑、port 不對，或這一次答不出來。',
    starting: '{{service}} 還在啟動，等一下再試一次。',
    auth_rejected: '{{service}} 不接受 Berth 的 API key。',
    auth_rejected_login: '{{service}} 不接受 Berth 的帳密。',
    auth_rejected_tmdb: 'TMDB 不接受這把 key。',
    ip_banned: '{{service}} 把 Berth 這台的 IP 封了：連續登入失敗太多次。',
    protocol_mismatch: '這個位址上回應的不是 {{service}}。',
    scheme_mismatch: '{{service}} 的位址寫 https://，但那個 port 講的是 http。',
    scheme_missing: '{{service}} 的位址沒寫 http:// 或 https://。',
    not_found: '{{service}} 說它沒有這個東西。',
    version_unsupported: '{{service}} 的版本 {{version}} 比 Berth 支援的下限舊。',
    login_rejected:
      '{{service}} 不收這組帳密：帳號至少要 3 個字元、不能有冒號，密碼至少要 6 個字元。',
    credential_missing: '還沒有憑證：貼上 key 再測。',
    category_conflict:
      'qBittorrent 已經有一個叫 {{category}} 的分類，存到 {{path}}；Berth 不改別人建的分類。',
    path_not_visible: 'Berth 的容器裡看不到 {{path}}。',
    directory_missing:
      'Berth 的容器裡沒有 {{path}} 這個目錄：它在 Berth 自己掛著的目錄底下，是這個目錄不見了。',
    berth_cannot_write: 'Berth 在 {{path}} 建不了目錄或寫不進檔案。',
    probe_unseen: 'qBittorrent 看不到 Berth 放在 {{path}} 的檔案：兩邊的這個路徑不是同一個目錄。',
    probe_unreadable: 'qBittorrent 找到了 Berth 放在 {{path}} 的檔案，但讀不了：是權限的問題。',
    probe_unsettled:
      'qBittorrent 在時限內沒有校驗完 Berth 放在 {{path}} 的檔案，它可能正忙著校驗別的；等一下重新檢查。',
    library_gone: 'Jellyfin 已經沒有「{{library}}」這個媒體庫了。',
    library_path_gone: '{{path}} 已經不是「{{library}}」的路徑了。',
    jellyfin_cannot_see:
      'Jellyfin 看不到 Berth 放在 {{path}} 的檔案：兩邊的這個路徑不是同一個目錄。',
    cross_device: '硬鏈接失敗：下載目錄與媒體庫在 Berth 裡是兩個不同的掛載。',
    link_failed: '硬鏈接失敗：這個位置的檔案系統或權限不讓 Berth 建硬鏈接。',
    site_cloudflare: '這個站擋自動化的請求（CloudFlare），要 FlareSolverr 才過得去。',
    site_no_results: '連得上這個站，但測試的那一次查詢什麼都沒回。',
    site_unreachable: 'Prowlarr 連不到這個站：它可能掛了，或這台主機連不出去。',
    site_rejected: 'Prowlarr 不肯加這個站。',
    site_not_offered: '這個站 Berth 加不了（不是公開的 torrent 站），要在 Prowlarr 自己加。',
    unexpected: '發生了沒預料到的錯誤。技術細節裡是原文。',
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
      jellyfin: '這裡只確認位址連得到、版本夠新。',
      qbittorrent: '免密的話帳密留空。',
      prowlarr: '在 Prowlarr 的「設定 → 一般 → 安全性」找得到 API key。',
    },
    probe:
      '測試時 Berth 會在 {{root}} 寫一個探測檔、請 qBittorrent 停住校驗一次，看它看不看得到 {{root}}，隨即移除（校驗不會跑完，不觸發「torrent 完成時執行外部程式」；你的 qBittorrent 設了「torrent 加入時執行外部程式」的話，會觸發一次），檔案也刪掉。',
    submit: '測試連線',
    submitting: '測試中…',
    notSaved: '這一組沒有存下：測得過才存。改好再按一次「測試連線」。',
    notSavedInUse: '這一組沒有存下：測得過才存，Berth 照舊用原本那一台。',
    error: {
      blank: '位址要填。',
      scheme: '位址要以 http:// 或 https:// 開頭，例如 http://192.168.1.10:8080。',
    },
    loopback:
      'Berth 在容器裡，這個位址指的是 Berth 自己，不是你的主機。改填 host.docker.internal（Docker Desktop 內建；Linux 由 compose 的 extra_hosts 提供，服務要監聽 0.0.0.0）或它的區網 IP。用 network_mode: host 部署的話，照填沒關係。',
    fix: {
      title: '手動步驟',
      unreachable: '在宿主上確認容器活著，再確認 port 沒有被改掉：',
    },
  },
  jellyfin: {
    unreachable: '讀不到 Jellyfin 這一步的狀態。確認 Berth 後端還在跑。',
    cutaway: {
      server: '這台 Jellyfin',
      apiKey: 'API key',
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
      admin_user: '以擁有者的帳密建立管理員（Jellyfin 那一頁）',
      libraries: '建立清單上的媒體庫',
      remote_access: '開啟遠端存取',
      complete: '結束初始精靈',
      api_key: '建立 Berth 專用的 API key',
    },
    bundled: {
      list: {
        title: '要建的媒體庫',
        lede: '內容類型、名稱與資料夾，照 Jellyfin 自己「新增媒體庫」的那三格。每一個都會成為一條 Route。',
        name: '名稱',
        type: '內容類型',
        types: {
          movies: '電影',
          tvshows: '劇集',
        },
        folder: '資料夾',
        unnamed: '第 {{position}} 個媒體庫',
        add: '加一個媒體庫',
        remove: '移除',
        removeNamed: '移除「{{name}}」',
        built: '已建立',
        builtHint:
          '已經建好的媒體庫在這裡改不動：要改名、刪除或換路徑，到 Jellyfin 的「控制台 → 媒體庫」。這裡只加還沒建的，重跑只建新加的那幾個。',
        saving: '儲存中…',
        unsaved: '清單有標紅的格子，改好才會存下來。',
        saveFailed: '清單沒存下來：請求沒跑完。確認 Berth 後端的狀態，再改一格試試。',
        refused: '清單沒存下來：{{reason}}',
        refusedRow: '清單沒存下來（第 {{position}} 個）：{{reason}}',
        problem: {
          empty: '至少要一個媒體庫。',
          name_missing: '名稱要填。',
          name_taken: '名稱重複了（不分大小寫）。',
          folder_missing: '名稱不是英文字母時，資料夾要自己填。',
          folder_taken: '資料夾重複了（不分大小寫）：兩個媒體庫會掃同一個目錄。',
          folder_outside_root: '資料夾是媒體庫根目錄底下的一層：不能有 / 或 \\，也不能是 . 或 ..。',
          folder_characters: '資料夾名不能有 < > : " | ? * 這些字元（Windows 不收）。',
          built_changed: '已經建好的媒體庫被改了。要改名或刪除，到 Jellyfin 做。',
        },
      },
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
      adding: '加入中…',
      // 逐個媒體庫的「加入 Berth 路徑」失敗（M4 票 19）。Jellyfin 自己只回 404，原因由 Berth 分辨。
      pathFailed: {
        title: '「{{library}}」沒加上 Berth 路徑',
        jellyfin_cannot_see:
          'Jellyfin 看不到 {{path}}：它沒掛 {{root}}。Berth 建好了目錄、在裡面寫了一個檔，Jellyfin 說它看不到；這一次建的目錄已經收回（原本就在的不動）。在你原本那一份 compose（或 docker run 指令）的 Jellyfin 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 {{root}}（${DATA_ROOT} 換成那個值）。原本的掛載不用動。重建它之後再按一次：',
        directory:
          'Berth 在自己的容器裡建不出 {{path}}：berth 少了 {{root}} 的掛載，或容器裡的使用者寫不進去。',
        jellyfin:
          'Jellyfin 沒有收下這一條（原文在上面）。確認它還連得上、Berth 的 API key 還有效，再按一次。',
        library_missing:
          'Jellyfin 上已經沒有「{{library}}」這個媒體庫了。按「重新讀取 Jellyfin 媒體庫」看它現在有哪些。',
      },
    },
    fix: {
      generic: '在你的 Jellyfin 上手動做這一步，然後回來重試。',
      public_info: '確認 Jellyfin 容器活著、版本是 12.0 以上，再確認位址與 port 沒有被改掉：',
      configuration: '在 Jellyfin 自己的初始精靈把語言設成繁體中文、地區設成台灣：',
      admin_user: '在 Jellyfin 自己的初始精靈建立管理員，帳密要與這裡 Jellyfin 那一頁一致：',
      libraries:
        '在 Jellyfin 的「媒體庫」手動建立清單上的媒體庫（名稱、類型與資料夾照左邊那一份），關掉即時監控、Specials 顯示名稱填 Specials：',
      remote_access: '在 Jellyfin 的初始精靈開啟遠端存取：',
      complete: '在 Jellyfin 自己的初始精靈按到最後一頁完成它：',
      api_key: '在 Jellyfin 的「API 金鑰」建立一把名為 Berth 的金鑰：',
      retryHint: '手動做完之後按下面的按鈕，Berth 只會重跑還沒完成的步驟。',
    },
  },
  interfaceLogin: {
    qbittorrent: {
      legend: 'qBittorrent WebUI 登入',
      lede: '這是 qBittorrent 自己的登入，給你之後打開它的 WebUI 用。Berth 自己用不到它（靠免密白名單進得去）；不設的話，WebUI 只剩容器 log 裡每次重啟都換的臨時密碼。',
      set: 'qBittorrent WebUI 的帳號：',
    },
    prowlarr: {
      legend: 'Prowlarr 介面登入',
      lede: '必填。這是 Prowlarr 自己的登入，給你之後打開它的介面用；Berth 用 API key，用不到它。Prowlarr 現行版本不讓介面沒有登入：沒在這裡設，第一次打開它會跳出關不掉的視窗要你設一組。設完它會自行重啟，要等一下。',
      set: 'Prowlarr 介面的帳號：',
    },
    username: '帳號',
    password: '密碼',
    confirm: '再輸入一次密碼',
    change: '更換登入',
    reuse: '沿用 Jellyfin 帳密（{{owner}}）',
    reuseHint:
      '帳號就是 {{owner}}，密碼打一次：Berth 先向 Jellyfin 確認它是對的才寫進去，只記雜湊、不存密碼。取消勾選就自己設一組。',
    ownerPassword: '{{owner}} 的 Jellyfin 密碼',
    carried: {
      applying: '沿用頁 1 的 Jellyfin 帳密（{{owner}}），設定中…',
      unfitLabel: '不能沿用',
      unfitPassword:
        '{{service}} 的密碼至少要 {{min}} 個字元，頁 1 那一組 Jellyfin 密碼太短，不能沿用；請在下面另設一組。',
      unfitUsername:
        '{{service}} 的帳號至少要 {{min}} 個字元、不能有冒號，{{owner}} 不能沿用；請在下面另設一組。',
    },
    error: {
      blank: '這一格要填。',
      mismatch: '兩次輸入的密碼不一樣。',
      usernameShort: '{{service}} 的帳號至少要 {{min}} 個字元。',
      usernameColon: '{{service}} 的帳號不能有冒號（:）。',
      passwordShort: '{{service}} 的密碼至少要 {{min}} 個字元。',
      reusePasswordShort:
        '{{service}} 的密碼至少要 {{min}} 個字元，這組 Jellyfin 密碼不能沿用；請取消勾選，另設一組。',
      reuseUsername:
        '{{service}} 的帳號至少要 {{min}} 個字元、不能有冒號，{{owner}} 不能沿用；請取消勾選，另設一組。',
    },
    refused: {
      owner_password: '這不是 {{owner}} 的 Jellyfin 密碼，所以什麼都沒寫；改好再按一次。',
      jellyfin_unreachable:
        '連不上 Jellyfin，驗不了這個密碼，所以什麼都沒寫。確認 Jellyfin 在跑再試一次。',
    },
    settings: {
      title: '介面登入',
      current: '目前的帳號是 {{username}}。改了之後舊的那一組就不能再用。',
      none: '還沒有設過。設一組之後，打開這個服務的介面就用它登入。',
      save: '更新登入',
      saving: '更新中…',
      saved: '已更新。之後用 {{username}} 登入，舊的那一組不能再用。',
      refused: '沒有確認到新的登入生效。用新的那一組試登入一次，不行就再按一次。服務回的原文：',
      failed: '這一次請求沒有走完，登入沒有變。確認 Berth 後端還在跑，再按一次。',
    },
  },
  qbittorrent: {
    title: {
      choose: '先選 qBittorrent 是哪一台',
      bundled: '設定 qBittorrent 的 WebUI 登入',
      existing: '確認你的 qBittorrent',
    },
    unreachable: '讀不到 qBittorrent 這一步的狀態。確認 Berth 後端還在跑。',
    lede: {
      choose:
        '兩種 Berth 都只用自己的分類，一個全域偏好都不寫；套件內的那一台另外由 Berth 設 WebUI 登入。選了 Berth 才去連它。',
      bundled:
        '這台 qBittorrent 是套件內的，Berth 只替它設 WebUI 登入，全域偏好一個都不寫。Berth 送出的 torrent 放進自己的 berth-* 分類（分類帶自己的完成與未完成目錄）、逐個開自動管理；你在它的介面上改預設儲存路徑不影響 Berth。',
      existing:
        '這台 qBittorrent 是你自己的，Berth 不改它的任何偏好，也不碰你既有的 torrent。Berth 送出的 torrent 放進自己的 berth-* 分類（分類帶自己的完成與未完成目錄）、逐個開自動管理；你不經 Berth 加的 torrent 照舊落在你自己的預設路徑。',
    },
    cutaway: {
      server: '這台 qBittorrent',
      webapi: 'Web API',
      password: 'WebUI 登入',
      willSet: '將設為下面填的那一組',
      existingLogin: '不改（這台是你自己的）',
      bundledPlan: '設定 WebUI 登入 · 只建 Berth 自己的分類',
      existingPlan: '只建 Berth 自己的分類 · 一個全域偏好都不寫',
    },
    step: {
      web_ui_password: 'WebUI 登入',
    },
    fix: {
      web_ui_password: '在「選項 → Web UI」自己設定帳號與密碼：',
      loginRejected:
        '照上面的規則改一組帳密，或取消「沿用 Jellyfin 帳密」另設一組，再按一次「設定介面登入」。',
    },
    blocked: {
      tooOld:
        'qBittorrent {{version}} 的 Web API 低於 2.8.4，Berth 要用的端點在那之前不存在。升級到 4.4 以上再回來。',
    },
    setLogin: '設定介面登入',
    settingLogin: '設定中…',
    done: '這個泊位的事做完了。WebUI 登入設好了；Berth 沒有改這台 qBittorrent 的全域偏好，它的下載走自己的分類。',
    doneExisting:
      '這個泊位的事做完了。Berth 沒有改這台 qBittorrent 的任何偏好，它的下載走自己的分類。',
  },
  indexer: {
    title: 'Prowlarr',
    lede: {
      choose:
        '先選 Prowlarr 是哪一台：套件內的那一台 Berth 讀得到它的 API key、替它加站與設介面登入；你自己的那一台貼 API key，用你已經有的站。',
      bundled:
        '索引站決定 Berth 找得到什麼。按一次，Berth 測試推薦的站、把通過的加進去；加入之後試搜，不要的就地移除。要逐站挑選或加其他公開站，展開「進階」。這一步可以之後再說。',
      existing:
        '索引站決定 Berth 找得到什麼。Berth 用你那一台已經有的站，可以試搜；也可以測試推薦的公開站、按一次加進去。Berth 不移除你的站。這一步可以之後再說。',
    },
    skip: '之後再說',
    deferred: '之後再說',
    unreachable: '連不上套件內的 Prowlarr。可以先填自己的位址，或跳過這一步之後再補。',
    readFailed: '讀不到這一台 Prowlarr 的站清單，所以說不出它有幾站。',
    rereadLater: '它可能正在重啟或暫時連不上：按「重新讀取」再試一次。',
    rereadKey:
      '多半是在 Prowlarr 重新產生了 API key。按「重新讀取」：Berth 會重讀掛載的 key 再連一次。',
    gap: {
      sites: '加入至少一個站',
      login: '設定 Prowlarr 介面登入',
    },
    cutaway: {
      title: 'Prowlarr',
      kind: '接法',
      bundled: '套件內 Prowlarr',
      existing: '你自己的 Prowlarr',
      added: '已加入',
      keyHeld: '已取得',
      keyRejected: '不被接受',
      keyUnverified: '已存下，還沒驗證',
      keyAbsent: '尚未取得',
    },
    connectFirst: '先在上面接上 Prowlarr，這裡才讀得到它的站。',
    quick: {
      title: '推薦站',
      lede_one:
        '按一次，Berth 測試推薦的 {{count}} 個公開站，把通過的加進 Prowlarr。Prowlarr 要現場連每一站，可能要一分鐘；有幾站連不上是常態，不影響其他站。',
      lede_other:
        '按一次，Berth 測試推薦的 {{count}} 個公開站，把通過的加進 Prowlarr。Prowlarr 要現場連每一站，可能要一分鐘；有幾站連不上是常態，不影響其他站。',
      run: '測試推薦站，加入通過的',
      running: '測試並加入中…',
      requestFailed: '測試與加入沒做完。',
      added_one: '加入 {{count}} 站',
      added_other: '加入 {{count}} 站',
      addFailed_one: '{{count}} 站測過、加不進去',
      addFailed_other: '{{count}} 站測過、加不進去',
      testFailed_one: '{{count}} 站沒通過測試',
      testFailed_other: '{{count}} 站沒通過測試',
      addFailedNote:
        '下面這幾站測試時連得上，Prowlarr 加入前自己再連一次卻沒連上，所以沒有加進去、也不算在已加入裡。這種站多半時好時壞：之後在「進階」裡再測、再加。',
      state: {
        added: '已加入',
        addFailed: '測過、加不進去',
        testFailed: '沒通過',
      },
      advanced: '進階：逐站測試與挑選、其他公開站',
    },
    add: {
      title: '加站',
      lede: '按「測試」時 Prowlarr 會現場連一次那個站，什麼都不建立；通過的才勾得起來。公開站有幾個連不上是常態，不影響其他站。每一站的說明是 Prowlarr 定義自帶的原文。',
      ledeExisting:
        '這裡加的站會加進你自己的 Prowlarr。按「測試」時它會現場連一次那個站，什麼都不建立；通過的才勾得起來，按「加入」才真的加。Berth 不移除站，要移除請到 Prowlarr 自己的介面。',
      intoYours_one: '按下去會把這 {{count}} 站加進你的 Prowlarr（{{host}}）：{{names}}。',
      intoYours_other: '按下去會把這 {{count}} 站加進你的 Prowlarr（{{host}}）：{{names}}。',
      recommended: '推薦的站',
      others: '其他公開站',
      othersLede: '這台 Prowlarr 認得的其他公開 torrent 站。輸入名稱或選一個語言才列出來。',
      filter: '搜尋名稱',
      language: '語言',
      anyLanguage: '全部語言',
      matches_one: '{{count}} 站符合',
      matches_other: '{{count}} 站符合',
      noMatch: '沒有符合的站。',
      test: '測試',
      testOne: '測試 {{name}}',
      testAll: '測試全部',
      testing: '測試中…',
      testFirst: '先測試，通過才勾得起來',
      semiPrivate: '半私有站，可能需要帳號',
      apply_one: '加入 {{count}} 個站',
      apply_other: '加入 {{count}} 個站',
      applyNone: '加入',
      applying: '加入中…',
      privateSites:
        '要帳號的站（私站、半私站）在 Prowlarr 自己的介面加，加完 Berth 就認得、可以試搜。',
      openProwlarr: '開啟 Prowlarr 的索引站頁',
      requestFailed: '測試沒有送到。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
      loading: '向 Prowlarr 讀站的清單…',
      login: '替 Prowlarr 介面設登入',
      loginFix:
        '帳密沒設成功，Prowlarr 的介面仍然是免登入的。設完它會自行重啟，所以也可能只是還沒回來。可以在它自己的介面上設：',
    },
    empty: {
      label: '待處理',
      body: '這一台 Prowlarr 還沒有任何站，Berth 什麼都搜不到。到 Prowlarr 加站後按「重新讀取」，或在下面測試推薦的公開站、勾起來加進去；也可以之後再說。',
      reread: '重新讀取',
      rereading: '讀取中…',
    },
    login: {
      required: '必填',
      save: '設定介面登入',
      saving: '設定中…',
    },
    added: {
      title: '已加入',
      listFailed: '列不出要問哪幾站：Berth 連不到 Prowlarr。確認它在跑，再搜一次。',
      sites_one: '{{count}} 站',
      sites_other: '{{count}} 站',
      lede: 'Prowlarr 只搜得到已經加入的站。每一列可以單獨搜，也可以一次搜全部；關鍵字留白就是問各站最新的發佈。',
      existingLede: '你那一台上已經有的站。Berth 用它們搜尋，不移除——要移除請到它自己的介面。',
      none: '這一台上還沒有任何站。',
      field: '關鍵字',
      placeholder: '留白＝各站最新的發佈',
      search: '搜尋',
      searchOne: '搜尋 {{name}}',
      searchAll: '搜尋全部',
      searching: '搜尋中…',
      pending: '還沒搜',
      count_one: '{{count}} 筆',
      count_other: '{{count}} 筆',
      searchFailed: '搜尋失敗',
      disabled: '在 Prowlarr 停用了',
      failed: '搜尋沒跑完。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
      keeps: '要帳號的站 Berth 不移除',
      done_one: '搜完了：{{count}} 站有結果。',
      done_other: '搜完了：{{count}} 站有結果。',
    },
    check: {
      untested: '未測',
      testing: '測試中',
      passed: '通過',
      failed: '沒通過',
    },
    failure: {
      cloudflare:
        '被 Cloudflare 擋住：這個站擋掉自動化的請求，要在 Prowlarr 設 FlareSolverr 才過得去。',
      no_results: '連得上，但測試那一次查詢什麼都沒回：站可能暫時空了或改了版，之後再測。',
      unreachable: '連不上：DNS、TLS 或站本身掛了。換個時間再測，或檢查 Prowlarr 那台對外的網路。',
      other: '沒通過，原因在 Prowlarr 的原文裡。',
    },
    summary: {
      failed_one: '{{count}} 站沒通過',
      failed_other: '{{count}} 站沒通過',
      passed_one: '{{count}} 站通過',
      passed_other: '{{count}} 站通過',
      reason: {
        cloudflare_one: 'Cloudflare 擋住 {{count}}',
        cloudflare_other: 'Cloudflare 擋住 {{count}}',
        no_results_one: '查無結果 {{count}}',
        no_results_other: '查無結果 {{count}}',
        unreachable_one: '連不上 {{count}}',
        unreachable_other: '連不上 {{count}}',
        other_one: '其他 {{count}}',
        other_other: '其他 {{count}}',
      },
      hint: '沒通過的勾不起來，之後可以再測。',
    },
    remove: {
      label: '移除',
      confirm: '確定移除',
      pending: '移除中…',
      warning: '從 Prowlarr 移除 {{name}}。之後要用，回到這裡測試通過再加入就好。',
      done: '已從 Prowlarr 移除 {{name}}。',
      failed: '移除沒成功。Prowlarr 可能正在重啟——等一下再按一次。',
    },
  },
  tmdbStep: {
    title: 'TMDB',
    lede: 'Berth 不內建任何一把 API key，TMDB 的憑證要你自己申請。這一步是必填的：沒有它就沒有標題、季集與封面，探索、命名與入庫全部停擺。',
    unreachable: '讀不到 TMDB 這一步的狀態。Berth 後端可能沒在跑——確認容器狀態後再試一次。',
    cutaway: {
      title: 'TMDB',
      credential: '憑證',
      endpoint: '測試打的端點',
    },
    required: '必填',
    held: '已取得',
    absent: '還沒填',
    whereLabel: '去哪裡拿',
    where:
      '在 themoviedb.org 註冊一個免費帳號，開「設定 → API」申請，用途選 Personal / Education，申請表要填一個網址與用途摘要。核發是即時的，不必等審核。',
    // 精靈裡多一句（`TmdbKey` 的 `inWizard`）：前半是同一段，用插值接上，不抄兩份。
    whereWizard: '{{where}}現在就去申請也沒關係——精靈的進度已經存下來了，回來時還在這一步。',
    open: '開啟 TMDB 的 API 設定',
    blank: '這一步要一把 key 才走得下去。貼上你在 themoviedb.org 拿到的那一把再按一次。',
    shape:
      '這不像 TMDB 的 key：API key 是 32 個英數字（0–9、a–f），read access token 是用兩個點分成三段的長字串。整串複製再貼一次。',
    field: '你的 TMDB API key',
    placeholder: '貼上 API key 或 read access token',
    hint: 'v3 的 API key（32 個十六進位字元）或 v4 的 read access token（很長的一串）都可以，貼哪一種都成立。',
    test: '測試 TMDB',
    testing: '測試中…',
    line: '驗證憑證',
    fix: '確認 key 沒有打錯，也確認這台機器連得到 api.themoviedb.org：',
    fixKey:
      'TMDB 不收這把 key：多半是貼錯、少貼了幾個字，或貼到帳號密碼。到 TMDB 的 API 設定頁重新複製「API 金鑰」或「API 讀取存取權杖」再測：',
    fixNetwork:
      '這台機器連不到 api.themoviedb.org：確認 Berth 的容器連得出去（DNS、防火牆、代理）。在宿主上跑這一行，印出 reachable 就是通的：',
  },
  routes: {
    title: '媒體庫路徑',
    lede: {
      bundled:
        '你列的每一個媒體庫各成為一條 Route：下載完成後硬鏈接到它的寫入目標。建好之後實際鏈接一個檔案，確認三個容器看到同一個檔案系統。第一次來、清單還是預設的時候，進這一頁就建立並檢查；改過清單就等你按「建立並檢查」。',
      existing:
        '勾選要交給 Berth 寫入的媒體庫，每個選一條寫入目標。Berth 只往你選的那一條寫，同一個媒體庫的其他路徑維持唯讀；不想讓它寫進你既有的資料夾，選「新的 Berth 路徑」，按「建立並檢查」時才加到 Jellyfin。進這一頁不會動任何東西。',
    },
    empty:
      '這台 Jellyfin 一個媒體庫都沒有。先在 Jellyfin 建一個再回來，Berth 才有地方寫入。Berth 不會替你的伺服器建媒體庫。',
    unreachable: '讀不到媒體庫清單。Berth 後端可能沒在跑——確認容器狀態後重新整理。',
    docking: '建立並檢查中…',
    list: '這一頁的 Route',
    tally: '{{passed}} / {{total}} 通過',
    // 跑到一半（M4 票 43）：每條纜繩開跑前後端先寫 running，頁 3 輪詢它。
    tallyRunning: '第 {{at}} / {{total}} 條 · {{check}}',
    // 健康迴圈不跑探針（M4 票 19、50）：那一條是沿用的結論，說出是哪一次。
    carried: {
      label: '沿用上一次的結論',
      why: '每 5 分鐘的自動檢查不重跑這一條：它會觸發 qBittorrent 的「torrent 完成時執行外部程式」。要再問一次，到 Route 設定按「{{recheck}}」。',
    },
    waiting: '等待中',
    autoRun: '預設清單沒改過，進這一頁就開始建立並檢查。要多一個媒體庫，等它跑完再展開清單加一列。',
    listSummary: '媒體庫清單',
    listPending_one: '{{count}} 個要建立',
    listPending_other: '{{count}} 個要建立',
    listBuilt_one: '{{count}} 個已建立',
    listBuilt_other: '{{count}} 個已建立',
    // 「建立並檢查」與按下之前列出的事（M4 票 08：進頁不動手，有副作用的由人按）。
    dock: {
      title: '按下之後會',
      build: '建立並檢查',
      libraries_one: '在 Jellyfin 建 {{count}} 個媒體庫：{{names}}',
      libraries_other: '在 Jellyfin 建 {{count}} 個媒體庫：{{names}}',
      berthPath: '在 Jellyfin 的「{{library}}」加入路徑 {{path}}（原本的路徑不動、不重新掃描）',
      categories_one: '在 qBittorrent 建或核對 {{count}} 個 berth- 分類（已經有的不改路徑）',
      categories_other: '在 qBittorrent 建或核對 {{count}} 個 berth- 分類（已經有的不改路徑）',
      probes_one:
        '在 {{count}} 條 Route 的分類路徑與寫入目標各寫一個探測檔（分類路徑那一個請 qBittorrent 停住校驗一次、隨即移除），做一次硬鏈接，檢查完就刪掉',
      probes_other:
        '在 {{count}} 條 Route 的分類路徑與寫入目標各寫一個探測檔（分類路徑那一個請 qBittorrent 停住校驗一次、隨即移除），做一次硬鏈接，檢查完就刪掉',
      probesYours_one:
        '在 {{count}} 條 Route 的分類路徑與寫入目標各寫一個探測檔（分類路徑那一個請 qBittorrent 停住校驗一次、隨即移除；你的 qBittorrent 設了「torrent 完成時執行外部程式」的話，每條會觸發一次），做一次硬鏈接，檢查完就刪掉',
      probesYours_other:
        '在 {{count}} 條 Route 的分類路徑與寫入目標各寫一個探測檔（分類路徑那一個請 qBittorrent 停住校驗一次、隨即移除；你的 qBittorrent 設了「torrent 完成時執行外部程式」的話，每條會觸發一次），做一次硬鏈接，檢查完就刪掉',
      listBlocked: '清單有標紅的格子，改好才能建立。',
      pickOne: '還差一步：勾一個媒體庫。',
      pickTarget: '還差一步：替「{{library}}」選一條寫入目標。',
      retryHint: '手動做完之後再按一次「建立並檢查」，已經建好的不會建第二次。',
    },
    recheck_one: '重新檢查 {{count}} 條 Route',
    recheck_other: '重新檢查 {{count}} 條 Route',
    // 頁 3 進頁時向 Jellyfin 重讀媒體庫（M4 票 19）：頁 1 之後在 Jellyfin 改的掛載與路徑要看得到。
    reread: '重新讀取 Jellyfin 媒體庫',
    rereading: '讀取中…',
    rereadFailed: '讀不到 Jellyfin 現在的媒體庫，下面是上一次讀到的那一份。',
    rereadDone_one: '已重新讀取：Jellyfin 上現在有 {{count}} 個媒體庫。',
    rereadDone_other: '已重新讀取：Jellyfin 上現在有 {{count}} 個媒體庫。',
    refused: {
      library_missing:
        'Jellyfin 上已經沒有你選的某個媒體庫了。按上面的「重新讀取 Jellyfin 媒體庫」，清單照 Jellyfin 現在的樣子重列，再按一次。',
      library_unsupported:
        'Berth 只寫入電影與劇集類型的媒體庫，選到的那一個不是。取消勾選它再按一次。',
      target_not_in_library:
        '選的寫入目標已經不是那個媒體庫的路徑了（Jellyfin 那邊剛改過）。按「重新讀取 Jellyfin 媒體庫」，重新選一次。',
      library_without_path:
        'Jellyfin 上有一個清單上的媒體庫沒有任何資料夾，Berth 不知道該寫到哪裡；重新整理也不會好。到 Jellyfin 的「控制台 → 媒體庫」替它加回資料夾，或在 Jellyfin 刪掉它，再按一次——Berth 會照清單把它建回來。是哪一個寫在技術細節裡。',
    },
    routeMissing:
      '這一步順便重新檢查了既有的 Route，其中一條在途中被刪掉了（多半是另一個分頁）。重新整理這一步，剩下的會再檢查一次。',
    cutaway: {
      paths: '路徑',
      libraryRoot: '媒體庫根目錄',
      completeRoot: 'complete 根目錄',
      plan: '將建立',
      library: '媒體庫',
      target: '寫入目標',
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
      newBerthPath: '新的 Berth 路徑：按「建立並檢查」時加到這個媒體庫，原本的路徑不動',
    },
    health: {
      unknown: '尚未檢查',
      ok: '已繫上',
      failed: '阻擋',
      checking: '檢查中',
    },
    check: {
      category: '建立 qBittorrent 分類',
      downloadPath: 'qBittorrent 的路徑 Berth 看得到',
      downloadVisible: 'qBittorrent 讀得到 Berth 寫的檔案',
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
      qbittorrentMount:
        'qbittorrent 容器少了這條路徑的掛載：Berth 在分類路徑寫了一個檔，qBittorrent 校驗之後說它一點都沒有——下載會寫進它自己的檔案層，Berth 拿不到。三個容器要把同一個宿主目錄掛在同一個容器路徑。改完 compose 之後跑 docker compose up -d：',
      libraryMount:
        'Jellyfin 報的這條媒體庫路徑不在三個容器共用的 {{root}} 底下，Berth 看不到。媒體庫要放在 {{root}} 底下，jellyfin 容器掛同一個宿主目錄。Route 建好之後寫入目標就鎖住了：在 Jellyfin 改好路徑之後，先刪掉這條 Route 再重新建立。改完 compose 之後跑 docker compose up -d：',
      berthCannotWrite:
        'Berth 自己寫不進 {{path}}：berth 容器裡的使用者（.env 的 PUID / PGID）沒有這個目錄的寫入權限，與別的容器的掛載無關。讓 berth 與 qBittorrent、Jellyfin 用同一組 PUID / PGID，或在宿主上把這個目錄的擁有者改成那一組（chown），再按「重新檢查」。',
      directoryMissing:
        'Berth 的容器裡沒有 {{path}}：掛載是好的（它在 Berth 掛著的 {{root}} 底下），是這個目錄被刪了或改了名。在宿主上把它建回來（擁有者是 berth 的 PUID / PGID），或到 {{service}} 改回原本的路徑，再按「重新檢查」。{{service}} 那邊仍看得到它的話，是兩邊的 {{root}} 掛的不是同一個宿主目錄。',
      hardlink:
        '鏈接不起來。complete 目錄與媒體庫目錄要在同一個檔案系統，容器裡的使用者也要寫得進去。',
      // 與掛載無關的失敗（M4 票 21）：連不到、帳密不對時給掛載片段只會叫人白改 compose。
      service: {
        unreachable: '確認 {{service}} 在跑、Berth 的容器連得到它，再按「重新檢查」。',
        auth: '{{service}} 不收 Berth 存的帳密或 API key：到 {{service}} 那一頁（設定裡也有）改好，再按「重新檢查」。',
      },
      probeUnreadable:
        'qBittorrent 容器裡的使用者讀不了 {{root}} 底下 Berth 寫的檔：讓它與 berth 用同一組 PUID / PGID，或放寬那個目錄的權限。',
      probeUnsettled: '等 qBittorrent 手上的校驗跑完，再按「重新檢查」。',
      libraryChanged:
        '到 Jellyfin 確認這個媒體庫與路徑還在。被刪掉或改了路徑的話，刪掉這條 Route、重新建立。',
      crossDevice:
        '這兩個目錄在 Berth 內是不同掛載（EXDEV）。硬鏈接跨不了掛載點——用一條掛載蓋住整個父目錄，不要 complete 與 library 各掛一條。網路磁碟、exFAT 隨身碟與 mergerfs 也做不到硬鏈接。',
      // 既有服務失敗在第 2–5 條時另說的那一句（M4 票 08，brief §16.4）：上面的 compose 片段是套件內那一份。
      existing: {
        qbittorrent:
          '這是你自己的 qBittorrent：它報的是它自己容器裡的路徑。Berth 要看得到同一個字串，兩者得在同一台主機、把同一個宿主目錄掛在容器路徑 /data（只能是 /data）。Berth 不做 remote path mapping——在 qBittorrent 原本的掛載之外多加這一條（原本的不用動），讓這條路徑在兩邊指到同一個地方。',
        qbittorrentMount:
          '你的 qBittorrent 看不到這個分類路徑：它多半沒掛 {{root}}（例如只掛了 /downloads），Berth 寫的檔在它那邊不存在。在你原本那一份 compose（或 docker run 指令）的 qBittorrent 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 {{root}}（${DATA_ROOT} 換成那個值；容器路徑只能是 {{root}}）。原本的掛載不用動：/downloads 留著，舊 torrent 照常做種，Berth 只在 {{root}} 底下讀寫。Berth 不做 remote path mapping。重建它（docker compose up -d，或刪掉容器再照新的指令 docker run）之後再按一次：',
        libraryMount:
          '你的 Jellyfin 把這個媒體庫放在它自己的容器路徑（例如 /movies、/tv），不在 {{root}} 底下，Berth 看不到。在你原本那一份 compose（或 docker run 指令）的 Jellyfin 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 {{root}}（${DATA_ROOT} 換成那個值）。原本的掛載不用動：/movies、/tv 留著——改了既有項目的路徑等於換成新項目、觀看紀錄歸零。Route 建好之後寫入目標就鎖住了：先刪掉這條 Route，再選「新的 Berth 路徑」當寫入目標。Berth 不做 remote path mapping：',
        jellyfinMount:
          '你的 Jellyfin 看不到 Berth 剛寫的檔案：它多半沒掛 {{root}}，或在另一台主機。在你原本那一份 compose（或 docker run 指令）的 Jellyfin 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在同一個容器路徑 {{root}}（${DATA_ROOT} 換成那個值）。原本的掛載不用動。Jellyfin 要與 Berth 在同一台主機；Berth 不做 remote path mapping：',
        split:
          '硬鏈接要 berth 只用一條掛載蓋住整個 /data：別為了配合你自己的服務，把下載與媒體庫拆成兩條掛進 berth。你的服務原本的 /downloads、/tv 留著，各自多掛一條同一個 /data 就好。',
      },
    },
  },
  complete: {
    doors: {
      title: '各服務自己的介面',
      lede: '平常用不到它們：Berth 替你接好了。要看下載細節、管理 Jellyfin 的使用者、在 Prowlarr 加要帳號的站時才開。',
      jellyfin: '用擁有者 {{name}} 登入，與 Berth 同一組。',
      bundledLogin: '帳號 {{name}}，密碼是精靈裡設的那一組。',
      instanceLogin: '帳號 {{name}}，密碼是這一台原本就有的那一組：這一輪精靈沒有設它。',
      noLogin: {
        qbittorrent:
          '還沒設 WebUI 登入：只有容器 log 裡每次重啟都換的臨時密碼。到「設定 → qBittorrent」設一組。',
        prowlarr: '還沒設介面登入：第一次打開它會要你設一組，或到「設定 → Prowlarr」設。',
      },
      yours: '用你原本的登入。',
      noLink: '給不出連結：Berth 只知道它在容器網路裡的位址。用你平常開它的那個位址。',
    },
    title: '完成設定',
    lede: '五個泊位都走過了。按下完成之後精靈就關閉，之後的修改在設定頁。',
    submit: '完成設定',
    completing: '完成中…',
    failed: '寫不進去。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    needTmdb:
      'TMDB 那一頁（頁 5）還沒完成：TMDB 要一把測得過的 key。沒有它，探索、季集快照與命名全部停擺，所以這一步不能跳。',
    needRoutes:
      '媒體庫路徑那一頁（頁 3）還沒完成：每一條 Route 的每一條纜繩都要綠燈。紅著的那一條，送單一定失敗。',
    unfinished: '還有一步沒做完，但這一頁看不出是哪一步。回上一步逐格看一次，紅的那一格就是。',
    pulledBack:
      '還不能完成：{{place}} 那一頁現在沒有做完——另一個分頁改過它，或它的檢查變紅了。先把這一頁做完，再走到完成。',
    fixTmdb: '回去填 TMDB key',
    signInHint:
      '完成後直接進 Berth。之後登入一律用 Jellyfin 帳號：你是 {{name}}，其他人用自己的 Jellyfin 帳號，是那台的管理員才進得來設定。',
    savePath: 'complete 目錄',
    skippedTitle: '跳過的步驟',
    cutaway: {
      title: '這一輪的結果',
      routes: 'Route 數',
      skipped: '跳過',
      nothing: '沒有',
    },
    skipped: {
      indexers: 'Prowlarr',
    },
    where: {
      indexers: 'Prowlarr 還沒接。之後在「設定 → Prowlarr」補上，補之前搜尋不到任何東西。',
      // 跳過了，但 Prowlarr 上本來就有站（重裝保留它的設定，M4 票 27）：搜尋照樣用得到。
      indexersPresent_one:
        '這一步跳過了，不過 Prowlarr 上已經有 {{count}} 個站，搜尋用得到它。加站與試搜在「設定 → Prowlarr」。',
      indexersPresent_other:
        '這一步跳過了，不過 Prowlarr 上已經有 {{count}} 個站，搜尋用得到它們。加站與試搜在「設定 → Prowlarr」。',
      indexersUnread:
        '這一步跳過了，這一次也讀不到 Prowlarr 的站清單。之後在「設定 → Prowlarr」確認或補上。',
    },
  },
  login: {
    code: 'BTH 0',
    title: '登船口',
    field: {
      username: 'Jellyfin 帳號',
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
    rss: 'RSS',
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
    // 這部作品的下載（M4 票 12，`.scratch/m4/media-downloads-shape.md`）。發佈名、檔名與字幕組不是文案。
    downloads: {
      title: '下載',
      filters: '這部作品的下載篩選',
      // 還沒了結＝還在路上的，加上已入庫、還有檔案等人確認的。
      filter: {
        open_one: '還沒了結 {{count}}',
        open_other: '還沒了結 {{count}}',
        all_one: '全部 {{count}}',
        all_other: '全部 {{count}}',
      },
      pages: '下載的分頁',
      pagesEnd: '下載清單底的分頁',
      noneOpen: '這部作品沒有還在路上或等你確認的下載。',
      off: '讀不到這部作品的下載。Berth 自己的 API 沒有回應，先確認它還活著。',
      retry: '重試',
      files: {
        title: '檔案',
        loading: '正在讀檔案清單…',
        none: 'qBittorrent 還沒給出這個 torrent 的檔案清單。',
        off: '讀不到檔案清單。Berth 自己的 API 沒有回應。',
        // priority 0：qBittorrent 不會下載它，計劃也不看它。
        unwanted: '不下載',
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
        // 後面接 resolver 下一次排在什麼時候。作品頁打開時已經先問過一次（M4 票 51），所以排程是 Berth 的，
        // 不是 Jellyfin 的。
        searching: 'Jellyfin 還在掃描，Berth 下一次確認在',
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
    indexers: '索引站',
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
    // 名字對上、年份或類型對不上的（M4 票 49）。收著不丟，展開看得到。
    onlyAside_one:
      '名字對得上的 {{count}} 筆，年份或類型都對不上這部作品，收在下面。自己打一個關鍵字也行。',
    onlyAside_other:
      '名字對得上的 {{count}} 筆，年份或類型都對不上這部作品，收在下面。自己打一個關鍵字也行。',
    setAside_one: '另有 {{count}} 筆年份或類型對不上這部作品，已經收起來。',
    setAside_other: '另有 {{count}} 筆年份或類型對不上這部作品，已經收起來。',
    off: '搜尋沒有送出去。Berth 自己的 API 沒有回應，先確認它還活著。',
    announce_one: '找到 {{count}} 筆，{{failed}} 個關鍵字沒問到。',
    announce_other: '找到 {{count}} 筆，{{failed}} 個關鍵字沒問到。',
    column: {
      title: '發佈名',
      size: '大小',
      seeders: '做種',
      indexer: '來源',
      estimate: '預估',
      published: '發佈',
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
    // 缺集分批（M3 票 20）：季號是機器字串，連接詞跟著語言走。
    batch: {
      preview: '分批問：這一批問 {{seasons}}。',
      laterPreview: '之後還有 {{later}} 批。',
      asked: '這一批問了 {{seasons}}。',
      next: '還有 {{later}} 批，下一批問 {{seasons}}。',
      last: '這是最後一批。',
      pending: '這一批要問 {{seasons}}，一個都還沒問。',
      ask: '問下一批',
      wait: '請求預算要到這時候才放得下它：',
      join: '、',
    },
    // 五種樣子，五種下一步。索引站是精靈裡唯一可以跳過的一步，所以「沒接」不是失敗。
    problem: {
      not_configured: {
        label: '還沒接',
        body: '設定精靈的第 6 步跳過了 Prowlarr，所以 Berth 沒有地方可以搜。接上 Prowlarr 之後這一區塊就會動。',
      },
      no_query: {
        label: '無法搜尋',
        body: 'Berth 還沒有這部作品的 TMDB 快照，所以不知道要拿什麼名字去問。到上面按「立即重抓」，或自己打一個關鍵字。',
      },
      credential_rejected: {
        label: '憑證被拒',
        body: '索引站不接受這把 API key。它可能被換掉了，或貼進來時少了幾個字。',
      },
      unreachable: {
        label: '連不上',
        body: '連不上索引站。可能是那個容器沒起來，或位址填錯了。',
      },
      // M3 票 20：不是壞了，是 Berth 自己先停手。等得到，所以不塗紅。
      budget_exhausted: {
        label: '等請求預算',
        body: '索引站背後的站這一小時的請求預算放不下這一批，一個關鍵字都沒問。RSS 輪詢、每日補漏與搜尋共用這一份，為的是不替你把公開站打到封 IP。',
      },
      retryAt: '放得下的時間：',
      askAdmin: '請管理員到設定接上索引站。',
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
    // Jellyfin 回驗（M3 票 17）：兩邊各自認成什麼。季集與 TMDB id 是機器字串，原樣顯示。
    differs: '不同的是',
    differsJoin: '、',
    differsWhat: { season: '季號', episode: '集號', tmdb: '作品' },
    ledgerReads: '帳本',
    jellyfinReads: 'Jellyfin 認成',
    noTmdb: '沒有 TMDB id',
    nextMismatch:
      '到 Jellyfin 修正它：作品認錯了用「識別」選回帳本那一部，兩份不同範圍的正片被併成一集就把其中一份移出去。修好之後按「重新反查」；下一次對帳比到一致時這一件也會自己收掉。',
    // 十四種型別各一句（brief §9.1）。
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
      jellyfin_item_mismatch: 'Jellyfin 認到的季集或作品與帳本不同',
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
      jellyfin_item_mismatch: '回驗不符',
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
        air_date_conflict: '發佈時間與換算出的集數的播出日對不上，季集多半算錯了',
        runtime_conflict: '量到的片長與 TMDB 那一集差太多，多半是特典或合併檔被當成正片',
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
      // 核准不帶表單上的值：改到一半的列擋住核准（M3 票 06）。`files` 是那幾列的檔名（`Intl.ListFormat` 串好）。
      unapplied: '還有改動沒有套用，先按「{{apply}}」或「{{cancel}}」：{{files}}',
      approve: '核准並入庫',
      reject: '拒絕',
      confirmReject: '丟掉這份計劃（包括逐列改過的），Berth 會重新規劃一次。檔案不動。',
      confirmRejectAction: '確定拒絕',
      working: '處理中…',
      approved: '已核准，開始入庫。',
      rejected: '已拒絕，Berth 重新規劃中。',
      failed: '沒有成功。Berth 自己的 API 沒有回應，先確認它還活著。',
      // 十三種擋下來的理由，各一個下一步。`detail`（檔名或路徑）接在後面。
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
        not_from_series:
          '這份計劃不是 RSS Series 送的，沒有 Series 可以套用。取消勾選「套用到這個 RSS Series」再試一次：',
        no_episode_number:
          '檔名讀不出集號，算不出集號偏移。取消勾選「套用到這個 RSS Series」，只改這一列：',
      },
      // 從審核裡套用到 RSS Series 之後，接在 Series 那一句後面：改的這一份沒有跟著核准。
      stillToApprove: '這一份照你改的留著，核准之後才入庫。',
    },
    // audit 那一列（CONTEXT.md 的 Audit）。
    audit: {
      label: '待確認',
      reason: {
        medium_auto_imported: '信心 medium，已自動入庫',
        // RSS Series 還沒確認：信心 high 的也在這裡（M3 票 13），要看的是季號與集數。
        first_batch: 'RSS Series 的第一批：看一眼季號與集數對不對',
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
        published_in_run: '季號是推測的（依發佈時間在播的那一輪）',
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
      // 同一個 RSS Series 的那一組（M3 票 13）。季號與偏移是 Series 現在的值（`rss.values`）。
      series: {
        firstBatch_one: 'RSS Series 的第一批：{{count}} 個檔案等你看一眼季號與集數對不對',
        firstBatch_other: 'RSS Series 的第一批：{{count}} 個檔案等你看一眼季號與集數對不對',
        name: 'RSS Series',
        values: '季號與偏移',
        unset: '沒有設，由解析器判斷',
      },
      confirmAll: '全部確認',
      // RSS Series 第一批那一組的那一顆：確認的是整個 Series 的季集對應，不只是畫面上這幾個檔案（M4 票 11）。
      confirmSeries: '確認整個 Series',
      // 整段的「全部確認」就地確認並說出件數；範圍是畫面上列出的那些。
      confirmSection_one:
        '這一段列出的 {{count}} 個已入庫檔案都會記成「對的」，檔案不動。按下之後才進來的不算在內。',
      confirmSection_other:
        '這一段列出的 {{count}} 個已入庫檔案都會記成「對的」，檔案不動。按下之後才進來的不算在內。',
      // 範圍裡有還沒確認的 RSS Series 時多說一句：它們的第一批一起確認，之後的 medium 不再進來。
      confirmSectionSeries_one:
        '其中 {{count}} 個 RSS Series 的第一批一起確認，之後它的 medium 入庫不再進這裡。',
      confirmSectionSeries_other:
        '其中 {{count}} 個 RSS Series 的第一批一起確認，之後它們的 medium 入庫不再進這裡。',
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
      // 改這一集的季集（`RematchForm`，M3 票 13）：只有正片有。
      correct: '改季集',
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
    // 套用到 RSS Series（M3 票 13）：搬的不只這一集。
    confirmMoveSeries:
      '媒體庫裡現在這一條會被拿掉、換到新的位置；這個 RSS Series 還沒確認的其他集數也照新的季號與偏移搬過去。complete 裡的檔案不動。',
    confirmAction: '確定修正',
    done: '已修正。',
    applyToSeries: '套用到這個 RSS Series',
    applyToSeriesHint: '寫回季號與集號偏移，重算這個 Series 還沒確認的集數。',
    // 套用之後說出 Series 現在的值，與其餘的集數怎麼了；是 0 的那幾句不說。
    series: {
      set: '已修正，這個 RSS Series 改成{{values}}。',
      moved_one: '其餘 {{count}} 集跟著搬過去了。',
      moved_other: '其餘 {{count}} 集跟著搬過去了。',
      replanned_one: '{{count}} 筆等審核的下載照新的值重新規劃了。',
      replanned_other: '{{count}} 筆等審核的下載照新的值重新規劃了。',
      left_one: '{{count}} 集搬不過去，留在原處等你看。',
      left_other: '{{count}} 集搬不過去，留在原處等你看。',
      nothingElse: '沒有其他還沒確認的集數要跟著改。',
    },
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
      not_from_series:
        '這個檔案不是 RSS Series 送的，沒有 Series 可以套用。取消勾選「套用到這個 RSS Series」再試一次：',
      no_episode_number:
        '檔名讀不出集號，算不出集號偏移。取消勾選「套用到這個 RSS Series」，只改這一集：',
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
    // 四個篩選（M4 票 04，`.scratch/m4/jobs-paging-shape.md`）。「在路上」＝還沒入庫也沒被移走，需要人的也在裡面。
    filters: '下載篩選',
    filter: {
      active_one: '在路上 {{count}}',
      active_other: '在路上 {{count}}',
      attention_one: '需要人 {{count}}',
      attention_other: '需要人 {{count}}',
      imported_one: '已入庫 {{count}}',
      imported_other: '已入庫 {{count}}',
      all_one: '全部 {{count}}',
      all_other: '全部 {{count}}',
    },
    pages: '分頁',
    pagesEnd: '清單底的分頁',
    // 看得見的是「1–50 / 523」，聽得見的是這一句。
    range: '第 {{first}}–{{last}} 筆，共 {{total}} 筆',
    rangeBeyond: '這一頁超出範圍，共 {{total}} 筆',
    // 篩完是空的：空的是這一組，不是整份清單，所以給一條去別組的路。
    emptyFilter: {
      active: '沒有在路上的下載：送出去的都入庫或移走了。',
      attention: '沒有需要你處理的下載。',
      imported: '還沒有入庫的下載。',
    },
    toFilter: {
      active: '看在路上的',
      imported: '看已入庫的',
    },
    emptyPage: '這一頁沒有下載：翻頁的當下清單變短了。',
    toFirstPage: '回第一頁',
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
      series_confirmed: '系統確認了 RSS Series',
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
      // 暫時失敗的送單（M4 票 03）：後面接一個相對時間（「10 分鐘後」）。
      resendAt: '第 {{attempt}} 次沒送成，自動再送：',
      resendSpent: '送了 {{attempt}} 次都沒成，不再自動送。修好之後按重試。',
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
      // RSS 自動綁定送出的那一筆（票 09）：沒有人選作品，時間線說出是憑什麼認的。
      grounds: '自動綁定，依據：',
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
        air_date_conflict: '發佈時間與播出日對不上',
        runtime_conflict: '片長與 TMDB 那一集對不上',
      },
      // 核准與拒絕（M2 票 07）。拒絕之後規劃器整份重算，所以下一筆就是新的那一份。
      reviewApproved_one: '管理員核准了，{{count}} 個檔案要入庫',
      reviewApproved_other: '管理員核准了，{{count}} 個檔案要入庫',
      reviewRejected: '管理員拒絕了這份計劃，Berth 重新規劃',
      // audit 的兩顆（M2 票 06）。目標路徑是機器字串，接在後面。
      auditConfirmed: '管理員看過這個 medium 自動入庫的檔案，說它是對的',
      // M4 票 11：第一批證據夠強，系統替人確認了那個 RSS Series。擔保的集數與 Series 名各另起一行。
      seriesConfirmed:
        '第一批的證據夠強，系統確認了這個 RSS Series：每一集都照檔名的集號對應、發佈時剛播出、播出日對得上。之後的集數照一般信心入庫。',
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
        round_failed: '上一輪的錯誤沒有再發生，這一輪處理完了。',
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
      // 算這一份時用的 RSS Series 值（M3 票 13）：之後改了 Series，這一份仍說它當時用了什麼。
      series: '照 RSS Series：{{values}}',
      seriesUnset: 'RSS Series 沒有設季號與集號偏移，由解析器判斷',
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
        air_date_conflict:
          '有檔案的發佈時間與換算出的那一集的播出日對不上：發佈比播出早，或比這部作品正在播的集數早很多。季號、offset 或絕對編號多半算錯了。管理員在審核佇列逐列改正季集；晚幾個月才發的 BD 版這種其實沒錯的，核准就會照畫面上的位置入庫。',
        runtime_conflict:
          'mediainfo 量到的片長與 TMDB 上那一集的片長差太多：多半是 SP、OVA 或兩集合併的檔案被當成了一集正片。管理員在審核佇列把那一列改成特典、對不到或正確的季集；片長其實沒錯的（TMDB 寫錯、剪輯版），核准就會照畫面上的位置入庫。',
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
        published_in_run:
          '只有集號；發佈於 {{published}}，那時在播的是 {{runs}} 輪裡的第 {{run}} 輪（從 {{episode}} 開始），集號照那一輪從 01 數',
        episode_not_on_tmdb: 'TMDB 第 {{season}} 季沒有第 {{number}} 集',
        absolute_within_first_season:
          '#{{number}} 沒有超過第 {{season}} 季的 {{episodes}} 集，也可能是後面某季重新從 01 數的第 {{number}} 集',
        air_date_unknown: '發佈說它在 {{aired}} 播出，但 TMDB 沒有 {{episode}} 的播出日',
        air_date_mismatch: '發佈說它在 {{aired}} 播出，TMDB 說 {{episode}} 在 {{tmdb_aired}}',
        range_spans_seasons: '發佈涵蓋 {{start}}–{{end}}，但那一段放不進同一季',
        specials_numbering: '字幕組的特典編號與 TMDB 的 S00 不一定一致',
        released_before_airing:
          '發佈於 {{published}}，比 TMDB 上 {{episode}} 的播出日 {{aired}} 早了兩天以上：集數多半換算錯了',
        behind_latest_episode:
          '{{episode}} 在 {{aired}} 播出，而發佈當時這部作品最近播出的是 {{latest}}（{{latest_aired}}）：季號或 offset 多半錯了',
        air_date_missing: 'TMDB 沒有 {{episode}} 的播出日，沒有比對發佈時間',
        published_missing: '來源沒有給發佈時間，沒有比對播出日',
        runtime_mismatch:
          'mediainfo 量到 {{measured}}，TMDB 上 {{episode}} 是 {{minutes}} 分鐘：差太多，多半是 SP、OVA 或兩集合併的檔案',
        runtime_missing: 'TMDB 沒有 {{episode}} 的片長，沒有比對片長',
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
        series_corrected:
          '同一個 RSS Series 改正過另一集，照第 {{season}} 季、集號偏移 {{offset}} 重算',
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
        published_run: '發佈時間',
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
        'Berth 還沒有 TMDB 憑證。它不內建任何一把，要你自己去 themoviedb.org 申請，再填進「設定 → TMDB」。',
      credential_rejected: 'TMDB 不接受這把憑證。它可能被撤銷了，或貼進來時少了幾個字。',
      unreachable: '連不上 TMDB。可能是這台機器沒有對外網路，或 TMDB 正在維護。',
      not_found: 'TMDB 上沒有這部作品。它可能已經被合併或刪除了——回探索頁重新找一次。',
      askAdmin: '請管理員到設定補上 TMDB 憑證。',
      retry: '重試',
    },
  },
  health: {
    title: '健康',
    failedLine: '這一輪的健康檢查沒通過：{{service}} 沒有回應，或回了錯誤。',
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
    // Jellyfin 專有：媒體庫數量（票 21）。其餘服務沒有這個數字。
    libraryCount_one: '{{count}} 個媒體庫',
    libraryCount_other: '{{count}} 個媒體庫',
    state: {
      ok: '已繫上',
      failed: '阻擋',
      unknown: '尚未檢查',
      unconfigured: '尚未接上',
    },
    // M3 票 20：一個站一份，三個使用者共用。延後不是壞了，所以不用「錯誤」的字。
    budget: {
      title: '請求預算',
      help: '每一站每小時最多 {{limit}} 個請求：RSS 輪詢、每日補漏與搜尋共用這一份，為的是不替你把公開站打到封 IP。重啟 Berth 會歸零。',
      idle: '這一小時還沒有問過任何站。',
      useCount: '{{use}} {{value}}',
      use: { poll: 'RSS 輪詢', backfill: '每日補漏', search: '搜尋', manual: '手動讀取' },
      deferred: '延後：{{use}}（擋下 {{value}} 個請求）',
      until: '放得下：',
      never: '一次要的比整份預算還多，放不下。',
    },
    poller: {
      title: '下載迴圈',
      lastRound: '上次輪詢',
      every: '有下載時每 {{seconds}} 秒',
      failures: '連續失敗',
      error: '最後的錯誤',
      errorLine: '上一輪問 qBittorrent 時失敗了。',
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
      empty: '還沒有 Route。到設定的「媒體庫路徑」新增一條，Berth 才有地方寫入。',
    },
    fix: {
      title: '修正',
      banned:
        'qBittorrent 因為連續登入失敗把 Berth 這台的 IP 封了。**改帳密沒有用**——那只會再失敗幾次，把封鎖時間重新算一輪。被封的是 qBittorrent 看到的來源 IP：Berth 經宿主的 port 或 host.docker.internal 連它時，那多半也是你瀏覽器的來源，所以這段時間你從宿主開它的 WebUI 也登不進去。等封鎖過期（qBittorrent 預設 1 小時），或到它的介面上把封鎖清掉；重啟 qBittorrent 容器也會清掉，因為封鎖只存在記憶體裡。確定帳密沒問題之後 Berth 下一輪就會自己變綠。',
      bundled:
        '這個服務是這套 compose 起的，所以先確認那個容器還在跑。三條指令的順序就是排查順序：還在嗎、把它起來、它自己說了什麼。',
      existing:
        '這是你自己的服務，Berth 只知道它現在回不出東西。位址或憑證變了的話到它的設定頁重新填一次。',
      unconfigured: '這個服務還沒接上。到它的設定頁接它——沒接上的話它負責的那件事一律不會發生。',
      askAdmin: '設定頁只有管理員進得去，請管理員來看。',
      unsupported:
        'Berth 需要 Jellyfin 12.0 以上（12.0 就是原本的 10.12）。升級前先把 Jellyfin 的 /config 完整備份 —— 12 改了資料庫，降不回去；再移除第三方插件，10.11 的插件在 12 載入不了。升級後完整掃描一次媒體庫。',
    },
  },
  // 設定頁（票 06i）：一格泊位一頁，精靈跑完之後改東西都在這裡。
  settings: {
    // 各處「去設定」的連結：說出會落在哪一頁（`SettingsHint`）。
    go: '前往設定：{{place}}',
    check: '重新檢查',
    checking: '檢查中…',
    checkFailed: '檢查沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
    health: '健康',
    tabs: {
      label: '設定',
    },
    connection: {
      title: '位址與憑證',
      lede: '與設定精靈那一頁的頁首是同一塊：按下去就存，然後真的連一次。上面那張卡會跟著重新檢查。',
      locked:
        '擁有者是這一台 Jellyfin 上的帳號，所以來源換不了；同一台換了位址可以在這裡改，另一台伺服器會被擋下。',
    },
    jellyfinPage: {
      title: 'Jellyfin 設定',
      lede: '這一台 Jellyfin 還連得上嗎、位址或 API key 要不要換，以及媒體庫上「在 Jellyfin 開啟」開在哪裡。',
      signIn: {
        title: '管理員登入',
        lede: 'Berth 用一把自己的 API key 跟 Jellyfin 說話。那把 key 被撤掉了，就用管理員重新登入一次換一把新的。',
      },
    },
    qbittorrentPage: {
      title: 'qBittorrent 設定',
      lede: '這一台 qBittorrent 還連得上嗎、位址或帳密要不要換，以及下載磁碟剩多少時開始擋送單。',
    },
    indexerPage: {
      sites: '站',
      title: 'Prowlarr 設定',
      lede: '加站、試搜、移除；接的是你自己的 Prowlarr 時，在這裡換網址或 key。',
    },
    tmdbPage: {
      title: 'TMDB 設定',
      lede: '換一把 TMDB API key。新的那一把測得過才換掉舊的；測不過的話舊的照舊在用，探索與入庫不受影響。',
      kept: '這一把測不過，沒有換掉——探索與入庫照舊用原本那一把。',
      failed: '測試沒有走完。Berth 後端可能沒在跑——確認容器狀態後再按一次。',
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
  },
  // Route 設定頁（票 14）。「Route」保留原文：它是 CONTEXT.md 的名詞，精靈與健康頁也這樣寫。
  routeSettings: {
    title: '媒體庫路徑',
    lede: '每條 Route 是一個 Jellyfin 媒體庫加上一條寫入目標；同一個媒體庫可以有好幾條，例如兩顆碟各一條。停用的 Route 不收新的送單；還有下載或入庫檔案指著它時，它刪不得。',
    empty: '還沒有 Route。用下面的「新增 Route」建一條，Berth 才有地方寫入。',
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
        '停用的 Route 不收新的送單，已經在路上的下載照常入庫。啟用時會先把每一條纜繩重跑一次。',
      identity:
        'slug 與寫入目標建立之後就不能改：分類、complete 子目錄與帳本都認它們。要換目標就新增一條、刪掉這一條。',
      save: '儲存',
      saveRechecks:
        '儲存會重跑下面每一條纜繩：那一輪會建 qBittorrent 分類，並在寫入目標寫一個探測檔。',
      saving: '儲存並檢查中…',
      saved: '已儲存。',
      unhealthy: '纜繩沒有全綠，這條 Route 維持停用。修好下面紅的那一條，再按一次儲存。',
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
      createdOk: '已建立「{{name}}」：纜繩全綠，已經啟用。',
      createdRed:
        '已建立「{{name}}」，但纜繩沒有全綠，所以維持停用。修好掛載之後在它那一列重新檢查，再勾啟用。',
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
  rss: {
    title: 'RSS',
    off: '讀不到 RSS 的清單。Berth 自己的 API 沒有回應，先確認它還活著。',
    // 一個 RSS Series 的季號與集號偏移（`rss/seriesValues.ts`）：審核的組、計劃、改正之後的那一句共用。
    values: {
      both: '第 {{season}} 季、集號偏移 {{offset}}',
      season: '第 {{season}} 季，集號不偏移',
      offset: '集號偏移 {{offset}}，季號由解析器判斷',
    },
    // 還沒確認的第一批在問什麼（M4 票 11，`rss/firstBatchAsk.ts`）：審核頁那一組與作品頁的「第一批待確認」。
    firstBatch: {
      ask: '確認 {{title}} × {{group}} 的季集對應：{{episodes}} {{basis}}',
      askUngrouped: '確認 {{title}} 的季集對應：{{episodes}} {{basis}}',
      separator: '、',
      basis: {
        literal: '由集號直接對應',
        series: '照 Series 設的季號與偏移換算',
        absolute: '由絕對集數換算',
        runs: '依播出的輪次換算（字幕組從 01 重數）',
        arc: '季號由篇章名讀出',
        mixed: '讀法不只一種',
      },
    },
    failed: '沒有做成。重新整理這一頁再試一次；還是不行的話看健康頁。',
    kind: { mikan: 'MIKAN', nyaa: 'NYAA', acgrip: 'ACG.RIP' },
    // 詳情頁的「RSS 訂閱」（M3 票 19，`media/SubscribePanel.tsx`）。
    subscribe: {
      title: 'RSS 訂閱',
      toRss: '到 RSS 頁',
      none: '還沒有 RSS Series 綁在這部作品上。',
      confirmed: '第一批已確認',
      firstBatch: '第一批待確認',
      latest: '最近：',
      nothingYet: '還沒有帶到任何一集。',
      start: '新增訂閱',
      label: '選一個來源建一條 feed，它帶來的集數都入庫到這部作品。',
      source: '來源',
      about: {
        mikan: '選番組與字幕組；整季補齊，之後的新集自動下載',
        nyaa: '以作品名搜尋；第一輪先給你看再決定',
        acgrip: '以作品名搜尋；第一輪先給你看再決定',
      },
      mikanSearch: '在 Mikan 搜番組',
      search: '搜尋',
      searching: '搜尋中…',
      noBangumi: 'Mikan 上沒有搜到番組。換一個名字試試（中文、日文、英文、羅馬字都可以）。',
      bangumi: '番組',
      reading: '讀這個番組的字幕組…',
      noSubgroups: '這個番組還沒有字幕組發佈。',
      subgroup: '字幕組',
      releases_one: '{{count}} 筆 · 最近 {{updated}}',
      releases_other: '{{count}} 筆 · 最近 {{updated}}',
      boundHere: '已經訂閱在這部作品上',
      boundElsewhere: '已經綁在另一部作品上（{{id}}）',
      confirm: '訂閱，只追之後的',
      confirmBackfill: '訂閱並補舊集',
      subscribing: '訂閱中…',
      subscribed_one: '已訂閱，送出 {{count}} 集。',
      subscribed_other: '已訂閱，送出 {{count}} 集。',
      titles: '這部作品的名字',
      term: '搜尋詞',
      termHint: {
        mikan: '',
        nyaa: 'Berth 以這個詞建一條 Nyaa 搜尋 feed（全部動畫分類）。',
        acgrip: 'Berth 以這個詞建一條 acg.rip 搜尋 feed。',
      },
      create: '建立搜尋 feed',
      creating: '建立並讀第一輪…',
      made: '「{{name}}」建好了。它帶來的每一個字幕組都綁在這部作品上；先看第一輪再決定要不要下載舊的。',
      decideLater: '之後在 RSS 頁決定',
      later: '搜尋 feed 建好了，第一輪等你在 RSS 頁決定。',
      unreachable: '現在讀不到 Mikan，什麼都沒加。等一下再試。原文：',
    },
    // `RssRefusal` 每一種各一句。原文另外印在下面（`detail`）。
    refusal: {
      feed_missing: '這個 Feed 已經不在了，多半是另一個分頁剛刪掉它。',
      feed_unsupported:
        '認不得這個網址。這一版收 Mikan（mikanani.me）、Nyaa（nyaa.si）與 acg.rip 的 RSS 網址。',
      feed_duplicate: '這個網址已經是一個 Feed 了。',
      series_missing: '這個 RSS Series 已經不在了。重新整理這一頁。',
      series_bound: '這個 RSS Series 已經綁好了，多半是另一個分頁剛綁的。要換作品先解除綁定。',
      media_missing: '讀不到這部作品的詳情。換一部再試，或等 TMDB 回來。',
      route_missing: '那條 Route 已經不在了。',
      route_disabled: '那條 Route 停用中。到設定的媒體庫路徑把它啟用，或換一條。',
      route_kind_mismatch: '那條 Route 收的不是這種作品（劇集只進得了劇集媒體庫）。',
      rule_invalid: '這條排除條件寫壞了，什麼都沒存。',
      feed_primed: '這個 Feed 的第一輪已經選過了，多半是另一個分頁剛選的。',
      feed_unreachable:
        '現在讀不到這個 feed，所以不知道「之前」是哪幾筆，什麼都沒改。等一下再選一次。原文：',
      feed_unread: '這個 Feed 還沒讀過。先按「立即輪詢」看過第一輪再選。',
      feed_not_rss:
        '讀到了，但那不是 RSS。多半是貼了網頁的網址：到站上找它的 RSS 連結（Mikan 番組頁字幕組旁的 RSS 圖示、Nyaa 搜尋結果頁的 RSS 鍵）。',
      budget_exhausted:
        '那一站這一小時的請求預算用完了，這一次沒有送出去。等預算放得下再試（健康頁看得到何時）。原文：',
    },
    feeds: {
      title: 'Feed',
      empty:
        '還沒有 Feed。到 Mikan 登入、訂閱想追的番組與字幕組，把「我的番組」頁上的 RSS 網址貼在下面。',
      add: '加一個 Feed',
      url: 'RSS 網址',
      urlHint:
        'Mikan「我的番組」的 RSS（/RSS/MyBangumi?token=…）或單一番組的 RSS；Nyaa 或 acg.rip 的搜尋 RSS。',
      name: '名稱（選填）',
      nameHint: '空著就用網址的主機名。',
      route: '自動綁定送進',
      routeNone: '不指定',
      routeHint:
        '認出來的作品有不只一條 Route 收得下時送進這一條。不指定時那幾部留在待綁定，由你選。',
      sendsTo: '自動綁定送進',
      addAction: '加入',
      count_one: '{{count}} 個 Feed',
      count_other: '{{count}} 個 Feed',
      toMikan: '打開 Mikan',
      adding: '加入中…',
      every: '每 {{minutes}} 分鐘',
      polled: '上次輪詢',
      items_one: '{{count}} 筆',
      items_other: '{{count}} 筆',
      // 上一輪抓不到 Feed，或有幾筆的單集頁抓不到（那幾筆下一輪再試）。
      failed: '上一輪有問題',
      undecided: '第一輪還沒決定，一筆都不送：在頁首選「只追之後的」或「全部下載」。',
      polledFailed: '這一輪沒讀到這個 Feed，什麼都沒改。原因在上面；背景下一輪會再讀。',
      polledNow:
        '這一輪：新 {{items}} 筆、長出 {{series}} 個 RSS Series（自動綁定 {{bound}} 個）、送出 {{sent}} 筆。',
      poll: '立即輪詢',
      polling: '輪詢中…',
      delete: '刪除',
      deleteConfirm: '刪除這個 Feed',
      deleteWarning_one:
        '會一起刪掉它的 {{count}} 筆 Feed Item。RSS Series 與綁定留著；之後加回同一個網址，已經送過的不會再送。',
      deleteWarning_other:
        '會一起刪掉它的 {{count}} 筆 Feed Item。RSS Series 與綁定留著；之後加回同一個網址，已經送過的不會再送。',
      deleting: '刪除中…',
    },
    pending: {
      title: '待綁定',
      chip_one: '{{count}} 個待綁定',
      chip_other: '{{count}} 個待綁定',
      lede: 'Feed 裡新出現的作品 × 字幕組。綁到 TMDB 上的作品與一條 Route 之後，留著的集數才會送出去。',
      label: '待綁定',
      waiting_one: '留著 {{count}} 集，綁定之後送出',
      waiting_other: '留著 {{count}} 集，綁定之後送出',
      // 自動綁定查過、沒有綁上的那一列（票 09）。下面接 `rss.grounds.*` 的句子。
      why: '沒有自動綁定：',
    },
    bind: {
      start: '綁定',
      label: '綁到哪一部作品',
      search: '搜尋 TMDB',
      searching: '搜尋中…',
      off: 'TMDB 現在搜不到東西。到健康頁看它怎麼了。',
      none: '沒有找到。換一個名字試試（英文名或原文名）。',
      results: '搜尋結果',
      reading: '讀取這部作品…',
      mediaOff: '讀不到這部作品的詳情，TMDB 可能暫時連不上。',
      willFreeze: '綁定之後資料夾名就定下來，之後 TMDB 改標題也不會動它：',
      alreadyFrozen: '這部作品的資料夾名已經定下來了：',
      willSend_one: '綁定之後會送出 {{count}} 集到 qBittorrent。',
      willSend_other: '綁定之後會送出 {{count}} 集到 qBittorrent。',
      confirm_one: '綁定並送出 {{count}} 集',
      confirm_other: '綁定並送出 {{count}} 集',
      // Mikan 的 RSS Series（票 12）：補幾集要讀了單一 feed 才知道，鍵上不說總數。
      backfill: '同時補下載舊集',
      backfillOn:
        '讀這個字幕組在 Mikan 上的整季，Feed 沒帶到的集數一起送出；媒體庫已經有、或已經下載過的跳過。之後每天再補一次漏掉的。',
      backfillOff: '只送 Feed 帶到的這幾集。更早的集數記成略過，之後每天的補漏也不會送它們。',
      confirmBackfill_one: '綁定、送出 {{count}} 集並補舊集',
      confirmBackfill_other: '綁定、送出 {{count}} 集並補舊集',
      binding: '綁定中…',
      kind: { tv: '劇集', movie: '電影' },
      done_one: '綁好了，送出 {{count}} 集。',
      done_other: '綁好了，送出 {{count}} 集。',
      // 自動綁定認出來、留給人選的作品（票 09）：按一下就選定它，接著挑 Route、確認。
      candidates: '候選',
      pick: '選《{{title}}》',
    },
    bound: {
      title: 'RSS Series',
      count_one: '{{count}} 個',
      count_other: '{{count}} 個',
      route: '入庫到 {{route}}',
      season: '第 {{season}} 季',
      offset: '集號偏移 {{offset}}',
      unbind: '解除綁定',
      unbindConfirm: '解除綁定',
      unbindWarning:
        '還沒送出去的集數回到待綁定；已經送出的下載與資料夾名不動。之後新出的集數會等你再綁一次。',
      unbinding: '解除中…',
      unbound: '已解除綁定。',
      // `bound_by = system`（票 09）：畫面說得出為什麼是這一部。
      automatic: '自動綁定',
      grounds: '依據：',
      // 以作品呈現（M4 票 13）：一列一個字幕組，件數與最近一筆。
      imported: '已入庫 {{n}}',
      active: '在路上 {{n}}',
      excluded: '排除 {{n}}',
      latest: '最近 {{episode}}',
      latestUnnumbered: '最近一筆',
      nothingYet: '還沒有發佈',
      finished_one: '已完結 {{count}} 個',
      finished_other: '已完結 {{count}} 個',
      finishedLede: '播完而且都入庫了，或 30 天沒有新的一筆。紀錄留著，新的一筆出現時回到上面。',
      allFinished: '沒有還在追的 RSS Series。',
      items: '它的 Feed Item',
      itemsLoading: '正在讀它的 Feed Item…',
      itemsOff: '讀不到它的 Feed Item。',
      itemsRetry: '重讀',
      itemsEmpty: '它的 Feed Item 跟著 Feed 刪掉了。',
      advanced: '進階',
    },
    // RSS Series 從哪裡來（M4 票 13）：說番組與字幕組的名字，不說 Mikan 的數字 id。
    source: {
      mikan: 'Mikan：{{bangumi}}',
      mikanGroup: 'Mikan：{{bangumi}} × {{group}}',
      mikanBare: 'Mikan',
    },
    // 自動綁定的理由（`domain.BindReasonCode`，票 09）。參數是原文，不翻譯；
    // 佔位符由 `tests/unit/test_bind_reasons.py` 對後端的參數表逐句比對。
    grounds: {
      title_equal: '「{{clue}}」與 TMDB 的「{{title}}」同名',
      premiere_near: 'Mikan 寫 {{premiere}} 開播，TMDB 第 {{season}} 季 {{aired}} 首播',
      release_near: 'Mikan 寫 {{premiere}}，TMDB 的上映日是 {{aired}}',
      season_airing:
        '名字寫第 {{season}} 季；Mikan 寫 {{premiere}} 開播，那時 TMDB 的這一季正在播（{{episode}} 在 {{aired}} 播出）',
      only_route: '收得下它的 Route 只有 {{route}}',
      feed_route: '收得下它的 Route 不只一條，這個 Feed 設定送進 {{route}}',
      no_candidate: 'TMDB 搜不到同名的作品',
      premiere_far: '同名的 {{title}} 沒有一季在 {{premiere}}（Mikan 寫的開播日）前後首播',
      several_candidates: '同名、開播日期也對得上的有 {{number}} 部',
      no_premiere: 'Mikan 的番組頁沒寫開播日期，年份無從確認',
      no_show_page: '這個來源沒有番組頁，年份無從確認：候選只從標題來，要你確認',
      lookup_failed: 'Mikan 番組頁或 TMDB 查不到（{{detail}}），留給你綁定',
      lookup_deferred: '{{site}} 這一小時的請求預算用完了，番組頁下一輪再讀',
      lookup_retry: '{{site}} 這一次讀不到（{{detail}}），{{at}} 再認一次（第 {{attempt}} 次重試）',
      route_ambiguous: '作品認出來了，但 {{routes}} 都收得下它',
      no_route: '作品認出來了，但沒有啟用中的 Route 收得下它',
    },
    // 排除條件（票 10）：三層共用一組字。
    rules: {
      title: '排除條件',
      lede: 'Feed 裡的項目預設全部下載，只擋這裡寫的。全域、Feed、RSS Series 三層取聯集，放在哪一層都擋。改了之後只影響還沒送出去的；拿掉一條不會把之前被它擋下的放回來。',
      notSingle: '不自動下載合集（不是單集的：合集、區間、季包）',
      notSingleHint: '合集照樣可以從搜尋或一次性 RSS 連結手動送單。',
      none: '沒有排除條件。',
      list: '排除條件',
      add: '加一條排除條件',
      hint: '一般字詞不分大小寫、比對整個標題；用 /…/ 包起來是正則（/…/i 不分大小寫）。',
      addAction: '加入規則',
      saving: '儲存中…',
      remove: '拿掉「{{rule}}」',
      suggestions: '建議',
      suggest: '加入「{{rule}}」',
      invalid: '存不進去：{{detail}}',
      toggle_one: '排除條件（{{count}} 條）',
      toggle_other: '排除條件（{{count}} 條）',
      feedLede: '只對這個 Feed，與全域的規則一起算。',
      seriesLede: '只對這個 RSS Series，與全域、Feed 的規則一起算。',
    },
    // 一筆 Item 為什麼沒下載（`domain.SkipCode`，票 10）。參數是原文，不翻譯；
    // 佔位符由 `tests/unit/test_skip_reasons.py` 對後端的參數表逐句比對。
    skip: {
      not_single: '不是單集（合集、區間或季包），預設不自動下載',
      global_rule: '全域的排除條件「{{rule}}」擋下',
      feed_rule: '這個 Feed 的排除條件「{{rule}}」擋下',
      series_rule: '這個 RSS Series 的排除條件「{{rule}}」擋下',
      same_torrent: '同一個 torrent 已經送過了（另一個 Feed 或手動送單）',
      in_library: '媒體庫裡已經有同一個版本：{{known}}',
    },
    // 新 Feed 的第一輪（票 11，`.scratch/m3/preview-shape.md`）。
    first: {
      title: '等你決定：新 Feed 的第一輪',
      chip_one: '{{count}} 個等你決定',
      chip_other: '{{count}} 個等你決定',
      lede: '搜尋 feed 第一輪就帶著好幾個月的歷史。選完之前，這個 Feed 一筆都不送。',
      unread:
        '第一輪還沒輪到：背景會在半分鐘內讀它，或在下方 Feed 段按「立即輪詢」。讀到之後這裡會列出每一筆。',
      unreadFailed: '還沒讀到過，選不了。背景下一輪再讀，或在下方 Feed 段按「立即輪詢」。上一次：',
      tally: {
        send_one: '會送出 {{count}}',
        send_other: '會送出 {{count}}',
        bind_one: '綁定之後送 {{count}}',
        bind_other: '綁定之後送 {{count}}',
        excluded_one: '排除 {{count}}',
        excluded_other: '排除 {{count}}',
        duplicate_one: '重複 {{count}}',
        duplicate_other: '重複 {{count}}',
      },
      group: {
        send_one: '會送出（{{count}} 筆）',
        send_other: '會送出（{{count}} 筆）',
        bind_one: '綁定之後送（{{count}} 筆）',
        bind_other: '綁定之後送（{{count}} 筆）',
        excluded_one: '排除（{{count}} 筆）',
        excluded_other: '排除（{{count}} 筆）',
        duplicate_one: '重複（{{count}} 筆）',
        duplicate_other: '重複（{{count}} 筆）',
      },
      show: '看{{name}}',
      bindHint: '它們的 RSS Series 在下方待綁定段，綁好之後才送。',
      later: '只追之後的',
      laterHint:
        '「只追之後的」會當場再讀一次 feed，現在已經在裡面的都略過，之後才出現的照常送。選完就定了；要重來得刪掉 Feed 再加一次。',
      all: '全部下載',
      allConfirm: '全部下載',
      allWarning:
        '會送出 {{send}} 筆到 qBittorrent，另外 {{bind}} 筆等它們的 RSS Series 綁好之後送。排除與重複的不送。',
      priming: '決定中…',
      donePassed_one: '《{{name}}》：只追之後的，略過 {{count}} 筆。',
      donePassed_other: '《{{name}}》：只追之後的，略過 {{count}} 筆。',
      doneSent_one: '《{{name}}》：全部下載，送出 {{count}} 筆。',
      doneSent_other: '《{{name}}》：全部下載，送出 {{count}} 筆。',
    },
    // 一次性 RSS 連結（票 18）：讀一次、勾幾筆走一般的送單，不建 Feed。
    oneshot: {
      title: '一次性 RSS 連結',
      lede: '貼一條 RSS 網址，讀一次、勾幾筆送出去。不會建立 Feed，之後出的集數不會自動下載。排除條件只管自動下載，這裡不擋：合集照樣勾得了。',
      url: '要讀的網址',
      urlHint: 'Mikan 單一番組的 RSS（/RSS/Bangumi?bangumiId=…），或 Nyaa、acg.rip 的搜尋 RSS。',
      read: '讀取',
      reading: '讀取中…',
      unreachable: '現在讀不到這個網址，等一下再按一次「讀取」。原文在下面。',
      empty: '這個 feed 裡一筆都沒有。',
      count_one: '讀到 {{count}} 筆',
      count_other: '讀到 {{count}} 筆',
      work: '送到哪一部作品',
      list: '勾選要送出的',
      pickAll_one: '勾選全部單集（{{count}} 筆）',
      pickAll_other: '勾選全部單集（{{count}} 筆）',
      pickNone: '全部取消',
      kind: { range: '區間', batch: '季包', collection: '合集' },
      hasJob: '這一筆已經有下載了。',
      known: '媒體庫裡已經有同一個版本：{{known}}',
      needWork:
        '選好作品與 Route 才送得出去；選了之後清單會照那部作品換算季集，並標出媒體庫已經有的。',
      willFreeze: '第一次送出時資料夾名就定下來，之後 TMDB 改標題也不會動它：',
      pickFirst: '勾幾筆再送出',
      send_one: '送出 {{count}} 筆',
      send_other: '送出 {{count}} 筆',
      sending: '送出中… {{done}}/{{total}}',
      stopped:
        '送到一半停下來了（已處理 {{done}} 筆）：Berth 沒有回應。沒送出的那幾筆還勾著，等一下再按一次。',
      done: '送出 {{sent}} 筆；{{already}} 筆本來就在了；{{refused}} 筆沒有送出。',
      outcome: { sent: '已送出', already: '本來就在了' },
    },
    series: {
      page: 'Mikan 番組頁',
    },
    items: {
      title: '最近的 Feed Item',
      count_one: '{{count}} 筆',
      count_other: '{{count}} 筆',
      empty: '還沒有 Feed Item。加一個 Feed、按「立即輪詢」。',
      published: '發佈於',
      job: '看這一筆下載',
      // 每一筆來自哪個 Feed、屬於哪個 Series（M4 票 13）。
      from: '來自',
      work: '{{work}} × {{group}}',
      unbound: '待綁定',
      status: {
        unbound: '待綁定',
        matched: '待送出',
        downloaded: '已送單',
        stuck: '送不出去',
        excluded: '已排除',
        duplicate: '重複',
        passed: '略過',
      },
      passed: '新 Feed 的第一輪選了「只追之後的」：這一筆在那之前就在了。',
    },
  },
  // 清單的上一頁 / 下一頁（`components/Pager`）：媒體庫的牆與下載列表共用。
  pager: {
    previous: '上一頁',
    next: '下一頁',
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
    library: 'Library paths',
    indexers: 'Prowlarr',
    tmdb: 'TMDB',
    indexerNone: 'No indexers added yet',
    indexerCount_one: '{{count}} indexer',
    indexerCount_other: '{{count}} indexers',
    routeCount_one: '{{count}} route',
    routeCount_other: '{{count}} routes',
    unassigned: 'Unassigned',
    waiting: 'Awaiting berth',
    summary: {
      expand: 'Show',
      collapse: 'Hide',
      blocked: 'Blocked',
    },
  },
  setup: {
    title: 'Setup wizard',
    stage: {
      berth: '{{code}}',
      final: 'Cast off',
    },
    step: 'Berth {{current}} of {{total}}',
    resumed: 'Progress is saved. Close the browser and you come back to this step.',
    statusFailed: 'Cannot read the wizard state.',
    notAdministrator:
      'Only a Jellyfin administrator can carry on with the wizard: {{name}} can sign in to Jellyfin but is not an administrator there. Sign out and sign in as an administrator.',
    nav: {
      label: 'Berth navigation',
      previous: 'Previous berth',
      next: 'Next berth',
      missing: 'Still to do',
    },
    stray: {
      where: 'Looking back: {{place}}',
      current: 'You are up to: {{place}}',
      back: 'Back to the current step',
    },
    revisit: {
      label: 'Looking back',
      can: 'You can do here',
      elsewhere: 'Not here',
      jellyfin: {
        can: 'See who the owner is. Once there is an owner the source is locked; if your existing Jellyfin moved (a new port, say), use “Change address” on the test result — only the same server is accepted.',
        elsewhere:
          'The owner’s password is changed in Jellyfin. Moving to another Jellyfin would mean another owner, which Berth does not support.',
        bundledCan:
          'See who the owner is. Once there is an owner the source is locked; the bundled one’s address comes from compose, so there is nothing to change.',
      },
      qbittorrent: {
        can: 'Switch between bundled and existing (this page starts over), change the existing one’s address or credentials, or change the bundled one’s WebUI login. No global preference is written.',
        elsewhere:
          'qBittorrent’s global preferences (default save path, automatic management…) are changed in qBittorrent itself; Berth neither writes nor reads them — its downloads only go through its own berth-* categories.',
      },
      routes: {
        can: 'The wizard only adds: a bundled Jellyfin can take more libraries on the list; newly ticked libraries get a route, and every check on every route runs again. Delete a wrong one underneath it.',
        elsewhere:
          'Renaming and disabling routes happens in Settings → Library paths once the wizard is finished.',
      },
      indexer: {
        bundled: {
          can: 'Switch between bundled and existing, test and add more public sites, run a trial search, remove the ones you do not want, change the interface login. Indexers already added are not added twice.',
          elsewhere:
            'Sites that need an account (private and semi-private) are added in Prowlarr itself.',
        },
        existing: {
          can: 'Switch between bundled and existing, re-read the site list, run a trial search; with a Prowlarr you can also test public sites and add them in one press. Indexers already added are not added twice.',
          elsewhere:
            'Removing sites, adding ones that need an account and changing the interface login all happen in your instance’s own interface; Berth does not remove your sites or touch its login.',
        },
      },
      tmdb: {
        can: 'Paste a key and test it again; a key that fails is still saved, so you can fix one character and press again.',
        elsewhere:
          'Requesting, revoking and reissuing the key itself happens under Settings → API on themoviedb.org.',
      },
    },
  },
  owner: {
    title: {
      choose: 'First, which Jellyfin?',
      create: 'Create the Jellyfin administrator',
      signIn: 'Sign in with your Jellyfin administrator',
      owned: 'Owner: {{name}}',
    },
    lede: {
      choose:
        'Berth has no accounts of its own; every sign-in goes through Jellyfin. So the first thing is to say which one: the one compose brought, or the one you already run. Berth only connects once you choose.',
      create:
        'Berth has no accounts of its own: this is the Jellyfin account you will sign in to Berth with. Berth creates the Jellyfin administrator with it, and you become the owner of Berth. Everyone else signs in with their own Jellyfin account, and Jellyfin decides their role.',
      signIn:
        'Berth has no accounts of its own; every sign-in goes through Jellyfin. Sign in with an administrator of this Jellyfin and you become the owner of Berth. Everyone else signs in with their own Jellyfin account, and Jellyfin decides their role.',
      owned:
        '{{name}} administers this Jellyfin and owns Berth. Sign in to Berth with this Jellyfin account from now on; its password is changed in Jellyfin.',
    },
    cutaway: {
      title: 'What happens',
      create: 'Creates',
      finish: 'Finishes',
      change: 'Changes',
      owner: 'Owner',
      form: 'Create or sign in',
      depends:
        'Once connected, it depends on that server: sign in if it has an administrator, create one if not',
      stored: 'Not stored',
      admin: 'The Jellyfin administrator',
      startup: "Jellyfin's startup setup",
      apiKey: 'API key “Berth”',
      nothing: 'Nothing on this Jellyfin',
      password: 'Your password (it only goes to Jellyfin)',
      passwordCarried:
        'Your password (it goes to Jellyfin, and becomes the bundled qBittorrent and Prowlarr interface password too)',
    },
    carry: {
      label: 'Use this login for the bundled qBittorrent and Prowlarr interfaces too',
      hint: 'Those two pages fill it in for you, so you do not type the password again; Berth still checks it with Jellyfin before writing it. The password stays only in this tab’s memory: Berth does not store it and the browser does not save it. After a reload you are asked again.',
    },
    field: {
      username: 'Jellyfin username',
      password: 'Password',
      confirm: 'Password again',
    },
    submit: {
      create: 'Create administrator and sign in',
      signIn: 'Sign in',
    },
    submitting: {
      create: 'Creating…',
      signIn: 'Signing in…',
    },
    refused: {
      jellyfin_unresolved:
        'Jellyfin is not connected yet. Get the test above to pass, then sign in.',
      invalid_credentials: 'Jellyfin does not accept that username or password.',
      not_administrator:
        'That account can sign in to Jellyfin but is not an administrator. The owner has to be able to change settings — sign in with an administrator of this Jellyfin.',
      jellyfin_failed:
        'Jellyfin did not finish: the error from that step is under technical details. Fix it and press again — nothing already done is redone.',
      owner_exists:
        'There is already an owner, and it is not replaced here. To give Berth a new API key, sign in again as an administrator in Settings → Jellyfin.',
      target_changed:
        'The Jellyfin address was changed while you were filling in the form, so your password was not sent. Test again, check that the address above is the one you mean, then send it again.',
    },
    saved: 'Owner · {{name}}',
    locked:
      'The owner is an account on this Jellyfin, so another Jellyfin would mean another owner — the source is locked. A new address for the same server is fine; another server is refused.',
    startup: {
      language: 'Language and region',
      languageHint:
        'Written into this Jellyfin’s own first-run settings: its interface language, and the language and country it fetches metadata in. Change them later in the Jellyfin dashboard.',
      remote: 'Allow remote access',
      remoteHint:
        'Lets devices outside your network reach this Jellyfin. Berth connects from a container on the same host and does not need it, so it is off by default.',
    },
    reSignIn: {
      title: 'Berth needs a new API key',
      lede: 'This Jellyfin no longer accepts the key Berth stored (most likely it was deleted under API Keys in Jellyfin). Sign in as one of its administrators and Berth gets a new one, then tests again.',
    },
    error: {
      blank: 'Username and password are both required.',
      mismatch: 'The two passwords do not match.',
      passwordSpaces: 'Jellyfin does not accept a password made only of spaces.',
      noPassword:
        'Berth does not take a Jellyfin account without a password as the owner: the owner can change every Berth setting, so no password means anyone can. Give this account a password under Dashboard → Users in Jellyfin, then sign in here.',
      username:
        "Jellyfin usernames can only use letters, numbers, spaces and - _ ' . @ +, and cannot be just “.” or “..”.",
    },
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
  },
  choice: {
    legend: 'Which {{service}} is this?',
    bundled: {
      title: 'Bundled',
      lede: 'The {{service}} compose brought along. Berth connects to it and sets it up for you:',
      absent: 'The {{service}} in this compose project is not running.',
      absentFix:
        'To use the bundled {{service}}: do whichever of the two below matches why it is not running, then pick “Bundled”. To connect your own, choose “Existing”.',
    },
    bringBack: {
      stopped: 'If the container stopped:',
      missing: 'If {{kind}} is not in COMPOSE_PROFILES:',
    },
    existing: {
      title: 'Existing',
      lede: 'The {{service}} you already run. Berth leaves your settings alone and {{adds}}',
      adds: {
        jellyfin:
          'only adds one path for Berth to write to on a library when you press the button on page 3 (the existing paths stay). If it has not run its own startup wizard yet, page 1 runs it with the account you enter.',
        qbittorrent:
          'only creates berth- categories when you press the button on page 3; the checks add one paused probe torrent and remove it right away. No preference is written.',
        prowlarr: 'only adds the sites you tick on page 4; the sites already there stay.',
      },
      sameHost:
        'Condition: it runs on the same host as Berth and also mounts Berth’s DATA_ROOT at the container path /data — it has to be /data, since Berth’s download and library folders sit underneath it. Its existing mounts stay as they are; adding this one is enough. DATA_ROOT has to be on a file system that supports hard links (not exFAT, a network share or mergerfs); one on another NAS cannot be connected.',
      library:
        'It needs libraries of the matching types (movies, shows) already: Berth does not create libraries on your Jellyfin, it only adds a path to the ones you tick on page 3.',
      profiles:
        'With an existing one, the bundled one is not needed: replace COMPOSE_PROFILES in .env with the first line ({{kind}} is left out), then stop the one already running with the second — changing COMPOSE_PROFILES and running docker compose up -d does not stop it. Forgetting is not fatal.',
      floor: {
        jellyfin:
          'Oldest supported: Jellyfin 12.0. Upgrading from 10.x is one-way, so read the upgrade notes first.',
        qbittorrent: 'Oldest supported: qBittorrent 4.4 (Web API 2.8.4).',
        prowlarr: 'Oldest supported: Prowlarr 1.3.2.',
      },
      upgradeNotes: 'Jellyfin 12.0 upgrade notes',
    },
    switchToBundled: 'Use the bundled one instead',
    saveFailed: 'The choice was not saved.',
    refused: {
      jellyfin_owned: 'Once there is an owner, the Jellyfin source cannot change.',
      other_server:
        'Not saved: another Jellyfin answers at this address, not the one the owner is on. The owner, Berth’s API key and the libraries are all on the original one; another server would mean another owner, which Berth does not support.',
      unverified:
        'Not saved: this address did not say which Jellyfin it is ({{detail}}), so Berth cannot tell whether it is the same one. Check the address and port, then try again.',
    },
    useBundled: 'Use the bundled {{service}}',
    useBundledLede:
      'Berth saves this choice and tests the {{service}} compose brought along (read-only).',
    switchAway: {
      jellyfin: 'Switching Jellyfin: this page starts over.',
      qbittorrent:
        'Switching qBittorrent: Berth never changed the preferences on yours; this page starts over, and library paths need checking again — the categories have to be created on the new one.',
      prowlarr: 'Switching Prowlarr: this page starts over.',
    },
    switchWarning: {
      qbittorrent:
        'Switching qBittorrent: this page starts over, and library paths need checking again — the categories have to be created on the new one.',
      prowlarr: 'Switching Prowlarr: this page starts over.',
    },
    leftovers: {
      reading: 'Reading what Berth created on the old one…',
      readFailed: 'Could not read what Berth created on the old one.',
      heading: 'What Berth created on the old one stays there after switching:',
      remembered:
        'The old one cannot be reached. This is what Berth remembers creating there; whether it is still there cannot be confirmed:',
      none: 'Berth created nothing on the old one.',
      noneRemembered: 'The old one cannot be reached; Berth remembers creating nothing there.',
      category: 'Category',
      empty: 'empty',
      torrents_one: '{{count}} torrent',
      torrents_other: '{{count}} torrents',
      sites: 'Indexers added',
      separator: ', ',
      login: 'Interface login set by Berth',
      removeEmpty_one: 'Remove {{count}} empty berth- category',
      removeEmpty_other: 'Remove {{count}} empty berth- categories',
      removed: 'The empty berth- categories were removed.',
      removeFailed: 'Nothing was removed.',
    },
  },
  connection: {
    state: {
      ok: 'Connected',
      waiting: 'Starting',
      failed: 'Failed',
      timeout: 'Timed out',
    },
    testing: 'Testing',
    untested: 'Not tested',
    result: 'Test result',
    waitingLabel: 'Waiting',
    waiting: '{{waited}} of {{window}} seconds',
    waitingHint:
      'The container is still starting. Berth tests again every 3 seconds until the limit.',
    retest: 'Test again',
    retesting: 'Testing…',
    announce: '{{service}} {{state}}: {{reason}}',
    edit: 'Change address or credentials',
    editAddress: 'Change address',
    pasteKey: 'Test again with this key',
    fix: {
      notDeployed:
        'This hostname does not resolve, so the {{kind}} container is not running: it may have stopped (a stopped container is not on the compose network), or it is not in COMPOSE_PROFILES in .env. Do whichever below matches, or choose “Existing” for your own one. Then press “Test again”.',
      somethingElse:
        'The limit has passed and something other than {{kind}} still answers on that hostname. Check that the compose service by that name is really it, or choose “Existing”.',
      apiKeyMissing:
        'Neither the read-only mount nor the environment has the Prowlarr API key. Copy it from Settings → General → Security in Prowlarr and paste it below; it stays bundled.',
      apiKeyEmpty:
        'Your own Prowlarr needs an API key before Berth can connect: copy it from Settings → General → Security, paste it into the field above and test again.',
      prowlarrMount:
        'Prowlarr does not accept the API key Berth read. Berth rereads config.xml from the read-only mount /ext/prowlarr on every test, so a key regenerated in Prowlarr is picked up: check that berth’s compose mounts ${CONFIG_ROOT}/prowlarr, then press “Test again”.',
      whitelist:
        'The bundled one asks for credentials: Berth’s password-free allowlist did not take. Restart it so the preseed script adds the allowlist, then test again:',
      bundledDown:
        'The container is not up yet. Check on the host that it is running, and read its log:',
      dataUnseen:
        'Your qBittorrent cannot see {{root}}: Berth wrote a file there and qBittorrent found none of it after a recheck. It most likely does not mount {{root}} (only /downloads, say), so downloads would land where Berth cannot reach them. Add one mount to the qBittorrent service in your own compose file (or to its docker run command): berth’s DATA_ROOT at {{root}} (replace ${DATA_ROOT} with the value in berth’s .env; the container path has to be {{root}}). Leave the mounts it already has: /downloads stays, old torrents keep seeding, and Berth only reads and writes under {{root}}. Berth does not do remote path mapping. Recreate it (docker compose up -d, or remove the container and docker run the new command), then test again:',
      dataUnseenBundled:
        'This compose’s qbittorrent cannot see {{root}}: Berth wrote a file there and qBittorrent found none of it after a recheck. Its mount for that path was changed in compose; put it back, run docker compose up -d qbittorrent, then test again:',
      dataUnreadable:
        'The user inside the qBittorrent container cannot read files Berth writes under {{root}}: give it the same PUID / PGID as berth, or loosen the permissions on that folder, then test again.',
      dataUnsettled: 'Let qBittorrent finish the checks it is running, then test again.',
      credentials: 'The username or password is wrong. Fix the fields above and test again.',
      authWarning:
        'Berth has counted {{failures}} failed logins in a row. By default qBittorrent bans this machine’s IP for {{minutes}} minutes after {{limit}}; at most {{left}} more and it will.',
      authWarningLast:
        'Berth has counted {{failures}} failed logins in a row; by default qBittorrent has banned this machine’s IP for {{minutes}} minutes by now. Fix the credentials, then test again once the ban expires or after restarting qBittorrent.',
      prowlarrKey:
        'The API key is wrong. Copy it from Settings → General in Prowlarr (not the interface password), paste it and test again.',
      banned:
        'By default qBittorrent bans an IP for {{minutes}} minutes after {{limit}} failed logins, and while banned even the right password is refused. The ban is on the source IP qBittorrent sees: when Berth reaches it through a host port or host.docker.internal, that is usually your browser’s source too, so its WebUI will refuse you from the host for the same time. Wait {{minutes}} minutes, or restart qBittorrent (it keeps bans only in memory); fix the credentials first, then test once after the ban is lifted.',
      address:
        "Nothing answers at this address. Check the port, that the service is running, and that Berth's container can reach that host.",
      schemeMismatch:
        'This port speaks http, not https: change https:// at the start of the address to http:// and test again.',
      schemeMissing:
        'The address has to start with http:// or https://, for example http://192.168.1.10:8080. Berth does not guess which.',
      outdated:
        'Berth needs at least {{floor}}; this one is {{version}}, and waiting will not change that. Upgrade it, then test again.',
      outdatedBundled:
        'Berth needs at least {{floor}}; the bundled one is {{version}}: pull a new image and start it again, then test again.',
      jellyfinKey:
        'This Jellyfin no longer accepts the API key Berth stored (most likely it was deleted under API Keys in Jellyfin). Sign in below as one of its administrators to get a new one.',
      otherServer:
        'Another Jellyfin now answers at this address. The owner, Berth’s API key and the libraries are all on the original one: point the address back at it, or check that no other container took that port.',
    },
  },
  reason: {
    connected: 'Connection test passed',
    setup_pending: 'Its startup wizard has not run yet',
    setup_completed: 'It already has an administrator',
    auth_required: 'API key not accepted',
    auth_required_login: 'Username or password not accepted',
    ip_banned: 'Has banned this machine (too many failed logins)',
    api_key_missing: 'No API key available',
    not_deployed: 'No host by that name',
    unreachable: 'The host is there, but nothing answers',
    starting: 'It answers, but says it is still starting up',
    coming_up: 'Still coming up; no proper answer yet',
    protocol_mismatch: 'Something answered, but it is not this service',
    scheme_mismatch: 'It answers, but this port speaks http, not https',
    scheme_missing: 'The address has no http:// or https://',
    version_unsupported: 'It answers, but it is older than the oldest version Berth supports',
    other_server: 'Another Jellyfin answers, not the one the owner is on',
    data_unseen: 'It answers, but it cannot see the file Berth put in /data',
    data_unreadable: 'It answers and finds the file Berth put in /data, but cannot read it',
    data_unsettled: 'It answers, but has not got to Berth’s probe file among its checks',
  },
  detail: {
    version: 'Version',
    server: 'Server',
    indexers: 'Indexers',
    tmdb: 'TMDB',
    credential: 'Credential',
    verified: 'Verified',
    unverified: 'Not verified',
    absent: 'Not entered',
  },
  technical: {
    title: 'Technical details',
  },
  request: {
    offline:
      'Berth’s backend did not answer: it may not be running, or the network dropped. Check the container and try again.',
    invalid:
      'Berth did not accept what was sent, most likely because this page is out of date. Reload and try again.',
    conflict:
      'This clashes with Berth’s current state (another tab may have just changed it). Reload and try again.',
    server:
      'Berth’s backend failed. Try again; if it keeps failing, read the berth container’s log.',
    signedOut: 'Your sign-in has expired: sign in to Berth again and retry.',
    ownerElsewhere:
      'The owner has already been set up elsewhere: another browser or tab finished this step first. Sign in as that Jellyfin administrator to carry on from where setup is now.',
    notAdministrator:
      'Only a Jellyfin administrator can do this: the account you signed in with is not an administrator on this Jellyfin.',
    signIn: 'Go to sign-in',
  },
  failure: {
    not_deployed:
      'The {{service}} hostname does not resolve: its container is not running, it is not part of this compose project, or the address is mistyped.',
    unreachable:
      'Cannot reach {{service}}: it is not running, the port is wrong, or it could not answer this time.',
    starting: '{{service}} is still starting. Try again in a moment.',
    auth_rejected: '{{service}} does not accept Berth’s API key.',
    auth_rejected_login: '{{service}} does not accept Berth’s username and password.',
    auth_rejected_tmdb: 'TMDB does not accept this key.',
    ip_banned: '{{service}} has banned this machine’s IP after too many failed logins.',
    protocol_mismatch: 'Whatever answers at this address is not {{service}}.',
    scheme_mismatch: 'The {{service}} address says https://, but that port speaks http.',
    scheme_missing: 'The {{service}} address has no http:// or https://.',
    not_found: '{{service}} says it has no such thing.',
    version_unsupported: '{{service}} {{version}} is older than the oldest version Berth supports.',
    login_rejected:
      '{{service}} refused this login: the username needs at least 3 characters and no colon, the password at least 6.',
    credential_missing: 'There is no credential yet: paste a key and test.',
    category_conflict:
      'qBittorrent already has a category called {{category}} that saves to {{path}}; Berth does not change a category it did not create.',
    path_not_visible: 'Berth’s container cannot see {{path}}.',
    directory_missing:
      'Berth’s container has no folder {{path}}: it is under a folder Berth mounts, so this folder itself is gone.',
    berth_cannot_write: 'Berth cannot create a folder or write a file at {{path}}.',
    probe_unseen:
      'qBittorrent cannot see the file Berth put in {{path}}: that path is not the same folder on both sides.',
    probe_unreadable:
      'qBittorrent found the file Berth put in {{path}} but cannot read it: this is a permissions problem.',
    probe_unsettled:
      'qBittorrent did not finish checking the file Berth put in {{path}} in time; it may be busy checking others. Check again later.',
    library_gone: 'Jellyfin no longer has a library called “{{library}}”.',
    library_path_gone: '{{path}} is no longer a path of “{{library}}”.',
    jellyfin_cannot_see:
      'Jellyfin cannot see the file Berth put in {{path}}: that path is not the same folder on both sides.',
    cross_device:
      'The hard link failed: the downloads and the library are two different mounts inside Berth.',
    link_failed:
      'The hard link failed: the file system or permissions there do not let Berth create one.',
    site_cloudflare: 'This site blocks automated requests (CloudFlare); it needs FlareSolverr.',
    site_no_results: 'The site answers, but the test query returned nothing.',
    site_unreachable:
      'Prowlarr cannot reach this site: it may be down, or this host cannot get out.',
    site_rejected: 'Prowlarr refused to add this site.',
    site_not_offered:
      'Berth cannot add this site (it is not a public torrent site); add it in Prowlarr itself.',
    unexpected: 'Something unexpected went wrong. The original message is under technical details.',
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
      jellyfin: 'This only confirms the address answers and the version is new enough.',
      qbittorrent: 'Leave the credentials empty if the WebUI has no password.',
      prowlarr: 'The API key is under Settings → General → Security in Prowlarr.',
    },
    probe:
      'The test writes a probe file in {{root}} and asks qBittorrent to check it once, stopped, to see whether it can see {{root}}, then removes it (the check never finishes, so “Run external program on torrent finished” does not fire; if your qBittorrent has “Run external program on torrent added” set, that fires once) and deletes the file.',
    submit: 'Test connection',
    submitting: 'Testing…',
    notSaved:
      'Nothing was saved: a connection is saved only once it passes. Fix it and test again.',
    notSavedInUse:
      'Nothing was saved: a connection is saved only once it passes. Berth keeps using the one it had.',
    error: {
      blank: 'The address is required.',
      scheme:
        'The address has to start with http:// or https://, for example http://192.168.1.10:8080.',
    },
    loopback:
      'Berth runs in a container, so this address points at Berth itself, not your host. Use host.docker.internal (built into Docker Desktop; on Linux the compose extra_hosts line provides it, and the service must listen on 0.0.0.0) or its LAN IP. If you deploy with network_mode: host, this is fine as it is.',
    fix: {
      title: 'Manual steps',
      unreachable:
        'Check the container is running on the host, then check the port was not changed:',
    },
  },
  jellyfin: {
    unreachable: 'Cannot read the state of this step. Check that the Berth backend is running.',
    cutaway: {
      server: 'This Jellyfin',
      apiKey: 'API key',
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
      admin_user: 'Create the administrator with the owner credentials (the Jellyfin page)',
      libraries: 'Create the libraries on the list',
      remote_access: 'Enable remote access',
      complete: 'Finish the startup wizard',
      api_key: 'Create an API key for Berth',
    },
    bundled: {
      list: {
        title: 'Libraries to create',
        lede: 'Content type, name and folder — the same three fields as “Add media library” in Jellyfin itself. Each one becomes a route.',
        name: 'Name',
        type: 'Content type',
        types: {
          movies: 'Movies',
          tvshows: 'Shows',
        },
        folder: 'Folder',
        unnamed: 'Library {{position}}',
        add: 'Add a library',
        remove: 'Remove',
        removeNamed: 'Remove “{{name}}”',
        built: 'Created',
        builtHint:
          'Libraries that already exist cannot be changed here: rename, remove or repath them under Dashboard → Libraries in Jellyfin. Here you can only add new ones, and a rerun creates only those.',
        saving: 'Saving…',
        unsaved: 'Fix the fields marked in red and the list will be saved.',
        saveFailed:
          'The list was not saved: the request did not finish. Check the Berth backend, then change a field to try again.',
        refused: 'The list was not saved: {{reason}}',
        refusedRow: 'The list was not saved (library {{position}}): {{reason}}',
        problem: {
          empty: 'Keep at least one library.',
          name_missing: 'Give it a name.',
          name_taken: 'That name is already on the list (case does not matter).',
          folder_missing: 'When the name is not plain ASCII, fill in the folder yourself.',
          folder_taken:
            'That folder is already on the list (case does not matter): two libraries would scan one directory.',
          folder_outside_root:
            'The folder is one level under the library root: no / or \\, and not . or ..',
          folder_characters: 'Folder names cannot contain < > : " | ? * (Windows refuses them).',
          built_changed:
            'A library that already exists was changed. Rename or remove it in Jellyfin.',
        },
      },
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
      adding: 'Adding…',
      pathFailed: {
        title: 'No Berth path was added to “{{library}}”',
        jellyfin_cannot_see:
          'Jellyfin cannot see {{path}}: it does not mount {{root}}. Berth created the directory and wrote a file in it, Jellyfin says it cannot see it; whatever this attempt created has been removed again (anything already there stays). Add one mount to the Jellyfin service in your own compose file (or to its docker run command): berth’s DATA_ROOT at {{root}} (replace ${DATA_ROOT} with the value in berth’s .env). Keep your existing mounts. Recreate it, then press again:',
        directory:
          'Berth could not create {{path}} in its own container: berth does not mount {{root}}, or the container user cannot write there.',
        jellyfin:
          'Jellyfin did not take this path (its reply is above). Check that it is still reachable and that Berth’s API key is still valid, then press again.',
        library_missing:
          'Jellyfin no longer has a library named “{{library}}”. Press “Read the Jellyfin libraries again” to see what it has now.',
      },
    },
    fix: {
      generic: 'Do this step by hand on your Jellyfin, then come back and retry.',
      public_info:
        'Check the Jellyfin container is running and on 12.0 or newer, then check the address and port were not changed:',
      configuration: "Set the language and metadata country in Jellyfin's own startup wizard:",
      admin_user:
        "Create the administrator in Jellyfin's own startup wizard, using the same credentials as the Jellyfin page here:",
      libraries:
        "Create the libraries on the list by hand under Jellyfin's Libraries (names, types and folders as on the left), with real-time monitoring off and Specials as the season-zero name:",
      remote_access: "Enable remote access in Jellyfin's startup wizard:",
      complete: "Finish Jellyfin's own startup wizard through to the last page:",
      api_key: "Create an API key named Berth under Jellyfin's API Keys:",
      retryHint:
        'Once you have done it by hand, press the button below — Berth only reruns the steps that are not finished.',
    },
  },
  interfaceLogin: {
    qbittorrent: {
      legend: 'qBittorrent WebUI login',
      lede: "This is qBittorrent's own login, for when you open its WebUI yourself. Berth does not need it (it gets in through the no-password allowlist); without it, the WebUI only has the temporary password in the container log, which changes on every restart.",
      set: 'qBittorrent WebUI username:',
    },
    prowlarr: {
      legend: 'Prowlarr interface login',
      lede: "Required. This is Prowlarr's own login, for when you open its interface yourself; Berth uses the API key and does not need it. Current Prowlarr versions do not allow an interface without a login: if you skip it here, the first time you open Prowlarr it shows a window you cannot close until you set one. Setting it restarts Prowlarr, so give it a moment.",
      set: 'Prowlarr interface username:',
    },
    username: 'Username',
    password: 'Password',
    confirm: 'Password again',
    change: 'Change login',
    reuse: 'Reuse the Jellyfin login ({{owner}})',
    reuseHint:
      'The username is {{owner}}; type the password once. Berth checks it with Jellyfin before writing it, and keeps only a hash, never the password. Untick to set a login of your own.',
    ownerPassword: "{{owner}}'s Jellyfin password",
    carried: {
      applying: 'Reusing the Jellyfin login from page 1 ({{owner}})…',
      unfitLabel: 'Cannot reuse',
      unfitPassword:
        '{{service}} needs a password of at least {{min}} characters; the Jellyfin password from page 1 is too short to reuse. Set one of its own below.',
      unfitUsername:
        '{{service}} needs a username of at least {{min}} characters with no colon, so {{owner}} cannot be reused. Set one of its own below.',
    },
    error: {
      blank: 'Fill this in.',
      mismatch: 'The two passwords differ.',
      usernameShort: '{{service}} needs a username of at least {{min}} characters.',
      usernameColon: '{{service}} does not allow a colon (:) in the username.',
      passwordShort: '{{service}} needs a password of at least {{min}} characters.',
      reusePasswordShort:
        '{{service}} needs a password of at least {{min}} characters, so this Jellyfin password cannot be reused; untick the box and set one of its own.',
      reuseUsername:
        '{{service}} needs a username of at least {{min}} characters with no colon, so {{owner}} cannot be reused; untick the box and set one of its own.',
    },
    refused: {
      owner_password:
        "That is not {{owner}}'s Jellyfin password, so nothing was written; fix it and press again.",
      jellyfin_unreachable:
        'Jellyfin could not be reached to check that password, so nothing was written. Check Jellyfin is running and retry.',
    },
    settings: {
      title: 'Interface login',
      current: 'The username is {{username}}. Once you change it, the old login stops working.',
      none: 'Not set yet. Set one and use it whenever you open this service yourself.',
      save: 'Update login',
      saving: 'Updating…',
      saved: 'Updated. Sign in as {{username}} from now on; the old login no longer works.',
      refused:
        'Could not confirm the new login took. Try signing in with it; if that fails, press again. What the service said:',
      failed:
        'The request did not finish and the login is unchanged. Check that the Berth backend is running, then press again.',
    },
  },
  qbittorrent: {
    title: {
      choose: 'First, which qBittorrent?',
      bundled: 'Set the qBittorrent WebUI login',
      existing: 'Check your qBittorrent',
    },
    unreachable: 'Cannot read the state of this step. Check that the Berth backend is running.',
    lede: {
      choose:
        'Either way Berth uses only its own categories and writes no global preference; on the bundled one Berth also sets the WebUI login. Berth only connects once you choose.',
      bundled:
        'This qBittorrent came with the bundle. Berth only sets its WebUI login and writes no global preference. Torrents Berth sends go into its own berth-* categories (each with its own completed and incomplete folders) with automatic management switched on per torrent; changing the default save path in its own UI does not affect Berth.',
      existing:
        'This qBittorrent is yours. Berth changes none of its preferences and none of your existing torrents. Torrents Berth sends go into its own berth-* categories (each with its own completed and incomplete folders) with automatic management switched on per torrent; anything you add yourself still lands in your own default folder.',
    },
    cutaway: {
      server: 'This qBittorrent',
      webapi: 'Web API',
      password: 'WebUI login',
      willSet: 'Will be set to the one entered below',
      existingLogin: 'Left alone (this one is yours)',
      bundledPlan: 'Sets the WebUI login · only creates Berth’s own categories',
      existingPlan: 'Only creates Berth’s own categories · writes no global preference',
    },
    step: {
      web_ui_password: 'WebUI login',
    },
    fix: {
      web_ui_password: 'Set the username and password yourself under Options → Web UI:',
      loginRejected:
        'Change the login to fit the rules above, or untick “Reuse the Jellyfin login” and set one of its own, then press “Set interface login” again.',
    },
    blocked: {
      tooOld:
        'qBittorrent {{version}} speaks a Web API older than 2.8.4, and the endpoints Berth needs did not exist yet. Upgrade to 4.4 or newer and come back.',
    },
    setLogin: 'Set interface login',
    settingLogin: 'Setting…',
    done: 'This berth is done. The WebUI login is set; Berth changed none of this qBittorrent’s global preferences, and its downloads go through its own categories.',
    doneExisting:
      'This berth is done. Berth changed none of this qBittorrent’s preferences; its downloads go through its own categories.',
  },
  indexer: {
    title: 'Prowlarr',
    lede: {
      choose:
        'First, which Prowlarr: on the bundled one Berth reads its API key, adds indexers and sets its interface login; for your own one paste its API key and Berth uses the indexers you already have.',
      bundled:
        'Indexers decide what Berth can find. One press tests the recommended sites and adds the ones that pass; then run a trial search and remove the ones you do not want. To pick sites one by one or add other public sites, open Advanced. This step can wait.',
      existing:
        'Indexers decide what Berth can find. Berth uses the indexers your instance already has and you can search them; you can also test the recommended public sites and add them in one press. Berth never removes your sites. This step can wait.',
    },
    skip: 'Do this later',
    deferred: 'Deferred',
    unreachable:
      'Cannot reach the bundled Prowlarr. Point Berth at your own instead, or skip this step and come back.',
    readFailed:
      "Could not read this Prowlarr's site list, so Berth cannot tell how many sites it has.",
    rereadLater: 'It may be restarting or briefly unreachable: press Re-read to try again.',
    rereadKey:
      'Most likely the API key was regenerated in Prowlarr. Press Re-read: Berth rereads the mounted key and connects again.',
    gap: {
      sites: 'Add at least one site',
      login: 'Set the Prowlarr interface login',
    },
    cutaway: {
      title: 'Prowlarr',
      kind: 'Connection',
      bundled: 'Bundled Prowlarr',
      existing: 'Your own Prowlarr',
      added: 'Added',
      keyHeld: 'Held',
      keyRejected: 'Not accepted',
      keyUnverified: 'Saved, not verified yet',
      keyAbsent: 'Not yet',
    },
    connectFirst: 'Connect Prowlarr above first; its sites show up here once Berth can reach it.',
    quick: {
      title: 'Recommended sites',
      lede_one:
        'One press: Berth tests the recommended public site and adds it to Prowlarr if it passes. Prowlarr reaches the site live, which can take a moment.',
      lede_other:
        'One press: Berth tests the {{count}} recommended public sites and adds the ones that pass to Prowlarr. Prowlarr reaches each site live, which can take a minute; a few being unreachable is normal and does not affect the rest.',
      run: 'Test recommended sites and add the ones that pass',
      running: 'Testing and adding…',
      requestFailed: 'Testing and adding did not finish.',
      added_one: '{{count}} site added',
      added_other: '{{count}} sites added',
      addFailed_one: '{{count}} site passed the test but could not be added',
      addFailed_other: '{{count}} sites passed the test but could not be added',
      testFailed_one: '{{count}} site did not pass the test',
      testFailed_other: '{{count}} sites did not pass the test',
      addFailedNote:
        'These sites were reachable during the test, but when Prowlarr connected again before adding them it could not get through, so they were not added and do not count as added. Sites like this tend to come and go: test and add them again later under Advanced.',
      state: {
        added: 'Added',
        addFailed: 'Passed, not added',
        testFailed: 'Did not pass',
      },
      advanced: 'Advanced: test and pick sites one by one, other public sites',
    },
    add: {
      title: 'Add indexers',
      lede: "Test asks Prowlarr to reach the site right now and creates nothing; only sites that pass can be ticked. A few public sites being unreachable is normal and does not affect the rest. Each site's description is the text from its Prowlarr definition.",
      ledeExisting:
        'Sites added here go into your own Prowlarr. Test asks it to reach the site right now and creates nothing; only sites that pass can be ticked, and nothing is added until you press Add. Berth does not remove sites — do that in Prowlarr itself.',
      intoYours_one: 'Pressing Add puts this site into your Prowlarr ({{host}}): {{names}}.',
      intoYours_other:
        'Pressing Add puts these {{count}} sites into your Prowlarr ({{host}}): {{names}}.',
      recommended: 'Recommended',
      others: 'Other public sites',
      othersLede:
        'The other public torrent sites this Prowlarr knows. Type a name or pick a language to list them.',
      filter: 'Search by name',
      language: 'Language',
      anyLanguage: 'Any language',
      matches_one: '{{count}} site matches',
      matches_other: '{{count}} sites match',
      noMatch: 'No site matches.',
      test: 'Test',
      testOne: 'Test {{name}}',
      testAll: 'Test all',
      testing: 'Testing…',
      testFirst: 'Test it first; only a site that passes can be ticked',
      semiPrivate: 'Semi-private; may need an account',
      apply_one: 'Add {{count}} site',
      apply_other: 'Add {{count}} sites',
      applyNone: 'Add',
      applying: 'Adding…',
      privateSites:
        'Sites that need an account (private and semi-private) are added in Prowlarr itself; once they are there Berth knows them and can search them.',
      openProwlarr: "Open Prowlarr's indexers page",
      requestFailed:
        'The test did not go through. The Berth backend may be down — check the container and try again.',
      loading: 'Reading the site list from Prowlarr…',
      login: 'Set the Prowlarr interface login',
      loginFix:
        'The credentials did not stick, so the Prowlarr interface is still open. Setting them restarts Prowlarr, so it may simply not be back yet. You can set them there yourself:',
    },
    empty: {
      label: 'To do',
      body: 'This Prowlarr has no sites yet, so Berth cannot find anything. Add sites in Prowlarr and press Re-read, or test the recommended public sites below and add the ones that pass; or do this later.',
      reread: 'Re-read',
      rereading: 'Reading…',
    },
    login: {
      required: 'Required',
      save: 'Set the interface login',
      saving: 'Setting…',
    },
    added: {
      title: 'Added',
      listFailed:
        'Could not list the sites to ask: Berth cannot reach Prowlarr. Check it is running and search again.',
      sites_one: '{{count}} site',
      sites_other: '{{count}} sites',
      lede: 'Prowlarr only searches sites that have been added. Search one row at a time or all of them at once; leave the keywords blank to ask each site for its latest releases.',
      existingLede:
        'The sites your instance already has. Berth searches with them and never removes any — remove them in its own interface.',
      none: 'This instance has no sites yet.',
      field: 'Keywords',
      placeholder: 'Blank = latest releases on each site',
      search: 'Search',
      searchOne: 'Search {{name}}',
      searchAll: 'Search all',
      searching: 'Searching…',
      pending: 'Not searched yet',
      count_one: '{{count}} result',
      count_other: '{{count}} results',
      searchFailed: 'Search failed',
      disabled: 'Disabled in Prowlarr',
      failed:
        'The search did not finish. The Berth backend may be down — check the container and try again.',
      keeps: 'Berth does not remove sites that need an account',
      done_one: 'Search finished: {{count}} site has results.',
      done_other: 'Search finished: {{count}} sites have results.',
    },
    check: {
      untested: 'Untested',
      testing: 'Testing',
      passed: 'Passed',
      failed: 'Did not pass',
    },
    failure: {
      cloudflare:
        'Blocked by Cloudflare: the site turns away automated requests. Prowlarr needs FlareSolverr to get through.',
      no_results:
        'Reachable, but the test query came back empty: the site may be empty for now or have changed. Test again later.',
      unreachable:
        "Unreachable: DNS, TLS or the site itself is down. Test again later, or check the Prowlarr host's outbound network.",
      other: "Did not pass; the reason is in Prowlarr's own text.",
    },
    summary: {
      failed_one: '{{count}} site did not pass',
      failed_other: '{{count}} sites did not pass',
      passed_one: '{{count}} site passed',
      passed_other: '{{count}} sites passed',
      reason: {
        cloudflare_one: 'Cloudflare {{count}}',
        cloudflare_other: 'Cloudflare {{count}}',
        no_results_one: 'no results {{count}}',
        no_results_other: 'no results {{count}}',
        unreachable_one: 'unreachable {{count}}',
        unreachable_other: 'unreachable {{count}}',
        other_one: 'other {{count}}',
        other_other: 'other {{count}}',
      },
      hint: 'Sites that did not pass cannot be ticked; test them again later.',
    },
    remove: {
      label: 'Remove',
      confirm: 'Remove it',
      pending: 'Removing…',
      warning:
        'Remove {{name}} from Prowlarr. To use it again later, come back here, test it and add it.',
      done: 'Removed {{name}} from Prowlarr.',
      failed: 'Removing it did not work. Prowlarr may be restarting — press again in a moment.',
    },
  },
  tmdbStep: {
    title: 'TMDB',
    lede: 'Berth ships no API key of its own, so this credential has to be yours. It is required: without it there are no titles, seasons or artwork, and browsing, naming and importing all stop.',
    unreachable:
      'Cannot read the state of the TMDB step. The Berth backend may be down — check the container and try again.',
    cutaway: {
      title: 'TMDB',
      credential: 'Credential',
      endpoint: 'Endpoint the test calls',
    },
    required: 'Required',
    held: 'Held',
    absent: 'Not set yet',
    whereLabel: 'Where to get one',
    where:
      'Sign up for a free account on themoviedb.org, then open Settings → API and request a key for Personal / Education use; the form asks for a URL and a short summary of what you are building. The key is issued immediately, with no review to wait for.',
    whereWizard:
      '{{where}} Going to get one now is fine — the wizard keeps its progress and comes back to this step.',
    open: "Open TMDB's API settings",
    blank:
      'This step needs a key to go on. Paste the one you got from themoviedb.org and press again.',
    shape:
      'That does not look like a TMDB key: an API key is 32 characters of 0–9 and a–f, a read access token is a long string split into three parts by two dots. Copy the whole thing and paste it again.',
    field: 'Your TMDB API key',
    placeholder: 'Paste an API key or a read access token',
    hint: 'Either a v3 API key (32 hex characters) or a v4 read access token (a long string) works — paste whichever you have.',
    test: 'Test TMDB',
    testing: 'Testing…',
    line: 'Verify the credential',
    fix: 'Check the key for typos, and check that this machine can reach api.themoviedb.org:',
    fixKey:
      'TMDB does not accept this key: most likely it was pasted wrong, cut short, or it is your account password. Copy the “API Key” or the “API Read Access Token” again from TMDB’s API settings and test:',
    fixNetwork:
      'This machine cannot reach api.themoviedb.org: check that Berth’s container can get out (DNS, firewall, proxy). Run this on the host; it prints reachable when it can:',
  },
  routes: {
    title: 'Routes',
    lede: {
      bundled:
        'Each library you list becomes a route: finished downloads are hard-linked into its write target. Once built, a real file is linked to prove all three containers see one file system. On your first visit with the default list, building and checking starts as you arrive; once you change the list, it waits for “Build and check”.',
      existing:
        'Tick the libraries Berth may write into and pick one write target for each. Berth writes only to the path you pick; the library’s other paths stay read-only. To keep Berth out of your existing folders, pick “new Berth path” — it is added to Jellyfin when you press “Build and check”. Arriving here changes nothing.',
    },
    empty:
      'This Jellyfin has no libraries. Create one in Jellyfin and come back, so Berth has somewhere to write. Berth does not create libraries on your server.',
    unreachable:
      'Could not read the library list. The Berth backend may be down — check the container, then reload.',
    docking: 'Building and checking…',
    list: 'Routes on this page',
    tally: '{{passed}} / {{total}} passed',
    tallyRunning: 'Check {{at}} of {{total}} · {{check}}',
    carried: {
      label: 'Carried over from the last probe',
      why: 'The automatic check every 5 minutes skips this one: it would fire qBittorrent’s “Run external program on torrent finished”. To ask again, press “{{recheck}}” in route settings.',
    },
    waiting: 'Waiting',
    autoRun:
      'The default list is unchanged, so building and checking started as you arrived. To add a library, wait for it to finish, then open the list and add a row.',
    listSummary: 'Library list',
    listPending_one: '{{count}} to create',
    listPending_other: '{{count}} to create',
    listBuilt_one: '{{count}} created',
    listBuilt_other: '{{count}} created',
    dock: {
      title: 'Pressing it will',
      build: 'Build and check',
      libraries_one: 'Create {{count}} library in Jellyfin: {{names}}',
      libraries_other: 'Create {{count}} libraries in Jellyfin: {{names}}',
      berthPath:
        'Add the path {{path}} to the Jellyfin library “{{library}}” (existing paths stay, no rescan)',
      categories_one:
        'Create or verify {{count}} berth- category in qBittorrent (existing ones keep their path)',
      categories_other:
        'Create or verify {{count}} berth- categories in qBittorrent (existing ones keep their path)',
      probes_one:
        'Write a probe file in the category path and the write target of {{count}} route (qBittorrent checks the first one while stopped, then it is removed) and make one hard link, all deleted once checked',
      probes_other:
        'Write a probe file in the category path and the write target of each of {{count}} routes (qBittorrent checks the first one while stopped, then it is removed) and make one hard link, all deleted once checked',
      probesYours_one:
        'Write a probe file in the category path and the write target of {{count}} route (qBittorrent checks the first one while stopped, then it is removed; if your qBittorrent runs an external program when a torrent finishes, it runs once per route) and make one hard link, all deleted once checked',
      probesYours_other:
        'Write a probe file in the category path and the write target of each of {{count}} routes (qBittorrent checks the first one while stopped, then it is removed; if your qBittorrent runs an external program when a torrent finishes, it runs once per route) and make one hard link, all deleted once checked',
      listBlocked: 'Fix the fields marked in red before building.',
      pickOne: 'One step left: tick a library.',
      pickTarget: 'One step left: pick a write target for “{{library}}”.',
      retryHint:
        'Once you have done it by hand, press “Build and check” again; what is already built is not built twice.',
    },
    recheck_one: 'Check {{count}} route again',
    recheck_other: 'Check {{count}} routes again',
    reread: 'Read the Jellyfin libraries again',
    rereading: 'Reading…',
    rereadFailed:
      'Could not read the libraries Jellyfin has now; below is the list Berth read last time.',
    rereadDone_one: 'Re-read: Jellyfin now has {{count}} library.',
    rereadDone_other: 'Re-read: Jellyfin now has {{count}} libraries.',
    refused: {
      library_missing:
        'A library you picked is no longer on Jellyfin. Press “Read the Jellyfin libraries again” above so the list matches Jellyfin, then press again.',
      library_unsupported:
        'Berth writes into movie and TV libraries only, and one you picked is neither. Untick it and press again.',
      target_not_in_library:
        'The write target you picked is no longer a path of that library (Jellyfin changed just now). Press “Read the Jellyfin libraries again” and pick again.',
      library_without_path:
        'A library on the list has no folder on Jellyfin, so Berth does not know where to write; reloading will not fix it. Give it a folder back under Dashboard → Libraries in Jellyfin, or delete it there and press again — Berth rebuilds it from the list. Which one is in the technical details.',
    },
    routeMissing:
      'This step also re-checks the routes you already have, and one of them was deleted while it ran — another tab, most likely. Reload this step and the rest will be checked again.',
    cutaway: {
      paths: 'Paths',
      libraryRoot: 'Library root',
      completeRoot: 'Complete root',
      plan: 'Will create',
      library: 'Library',
      target: 'Write target',
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
      newBerthPath:
        'New Berth path: added to this library when you press “Build and check”; existing paths stay',
    },
    health: {
      unknown: 'Not checked',
      ok: 'Ready',
      failed: 'Blocked',
      checking: 'Checking',
    },
    check: {
      category: 'Create the qBittorrent category',
      downloadPath: 'Berth sees the qBittorrent paths',
      downloadVisible: 'qBittorrent reads the file Berth wrote',
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
      qbittorrentMount:
        'The qbittorrent container is missing a mount for this path: Berth wrote a file in the category path and qBittorrent found none of it after a recheck, so downloads would land in its own container layer where Berth cannot reach them. All three containers must mount the same host directory at the same container path. After editing compose, run docker compose up -d:',
      libraryMount:
        'Jellyfin reports a library path outside {{root}}, the directory all three containers share, so Berth cannot see it. Keep libraries under {{root}} and mount the same host directory in the jellyfin container. A route’s write target is fixed once it is created: after changing the path in Jellyfin, delete this route and create it again. After editing compose, run docker compose up -d:',
      berthCannotWrite:
        'Berth itself cannot write to {{path}}: the user inside the berth container (PUID / PGID in .env) has no write permission on that folder. The other containers’ mounts have nothing to do with it. Give berth the same PUID / PGID as qBittorrent and Jellyfin, or make that PUID / PGID the owner of the folder on the host (chown), then press “Check again”.',
      directoryMissing:
        'Berth’s container has no {{path}}: the mount is fine (it is under {{root}}, which Berth mounts), this folder was deleted or renamed. Create it again on the host (owned by berth’s PUID / PGID), or change {{service}} back to the original path, then press “Check again”. If {{service}} can still see it, the two sides mount different host directories at {{root}}.',
      hardlink:
        'The link failed. The complete directory and the library directory have to sit on one file system, and the container user has to be able to write there.',
      service: {
        unreachable:
          'Check that {{service}} is running and that Berth’s container can reach it, then press “Check again”.',
        auth: '{{service}} does not accept the credentials or API key Berth stored: fix them on the {{service}} page (it is under settings too), then press “Check again”.',
      },
      probeUnreadable:
        'The user inside the qBittorrent container cannot read files Berth writes under {{root}}: give it the same PUID / PGID as berth, or loosen the permissions on that folder.',
      probeUnsettled: 'Let qBittorrent finish the checks it is running, then press “Check again”.',
      libraryChanged:
        'Check in Jellyfin that this library and its path still exist. If it was deleted or its path changed, delete this route and create it again.',
      crossDevice:
        'Those two directories are separate mounts inside Berth (EXDEV). A hard link cannot cross a mount point: use one mount covering the whole parent directory instead of mounting complete and library separately. Network shares, exFAT drives and mergerfs cannot hard-link either.',
      existing: {
        qbittorrent:
          'This is your own qBittorrent: the path it reports is a path inside its own container. For Berth to see the same string, both must run on the same host and mount the same host directory at the container path /data (it has to be /data). Berth does no remote path mapping — add this one mount to qBittorrent next to its existing ones (keep those as they are), so this path points at the same place in both.',
        qbittorrentMount:
          'Your qBittorrent cannot see this category path: it most likely does not mount {{root}} (only /downloads, say), so the file Berth wrote does not exist on its side. Add one mount to the qBittorrent service in your own compose file (or to its docker run command): berth’s DATA_ROOT at {{root}} (replace ${DATA_ROOT} with the value in berth’s .env; the container path has to be {{root}}). Keep your existing mounts: /downloads stays, your old torrents keep seeding, and Berth only reads and writes under {{root}}. Berth does no remote path mapping. Recreate it (docker compose up -d, or remove the container and docker run the new command), then press again:',
        libraryMount:
          'Your Jellyfin keeps this library at a path of its own (/movies or /tv, say), outside {{root}}, so Berth cannot see it. Add one mount to the Jellyfin service in your own compose file (or to its docker run command): berth’s DATA_ROOT at {{root}} (replace ${DATA_ROOT} with the value in berth’s .env). Keep your existing mounts: /movies and /tv stay — changing the path of existing items turns them into new items and resets watch history. A route’s write target is fixed once it is created: delete this route, then pick “new Berth path” as the write target. Berth does no remote path mapping:',
        jellyfinMount:
          'Your Jellyfin cannot see the file Berth just wrote: it most likely does not mount {{root}}, or runs on another host. Add one mount to the Jellyfin service in your own compose file (or to its docker run command): berth’s DATA_ROOT at the same container path {{root}} (replace ${DATA_ROOT} with the value in berth’s .env). Keep your existing mounts. Jellyfin has to run on the same host as Berth; Berth does no remote path mapping:',
        split:
          'A hard link needs berth to cover all of /data with one mount: do not split downloads and media into two mounts in berth to match your own services. Keep your existing mounts on those services (/downloads, /tv) and add the same /data to each.',
      },
    },
  },
  complete: {
    doors: {
      title: 'The services’ own interfaces',
      lede: 'You will rarely need them: Berth has wired them up. Open them to see download details, manage Jellyfin users, or add sites that need an account in Prowlarr.',
      jellyfin: 'Sign in as the owner, {{name}} — the same account as Berth.',
      bundledLogin: 'Username {{name}}; the password is the one you set in the wizard.',
      instanceLogin:
        'Username {{name}}; the password is the one it already had — this run of the wizard did not set it.',
      noLogin: {
        qbittorrent:
          'No WebUI login yet: only the temporary password in the container log, which changes on every restart. Set one in Settings → qBittorrent.',
        prowlarr:
          'No interface login yet: it asks you to set one the first time you open it, or set one in Settings → Prowlarr.',
      },
      yours: 'Use the login you already have.',
      noLink:
        'No link: Berth only knows its address inside the container network. Use the address you normally open it at.',
    },
    title: 'Finish setup',
    lede: 'All five berths have been visited. Finishing closes the wizard; later changes happen in Settings.',
    submit: 'Finish setup',
    completing: 'Finishing…',
    failed: 'Could not save. The Berth backend may be down — check the container and press again.',
    needTmdb:
      'The TMDB page (page 5) is not finished: TMDB needs an API key that passes its test. Without it discovery, episode snapshots and naming all stop, so this step cannot be skipped.',
    needRoutes:
      'The library paths page (page 3) is not finished: every check has to pass on every route. Submitting to a red one always fails.',
    unfinished:
      'A step is still unfinished, but this page cannot tell which. Go back a step and look at each berth — the red one is it.',
    pulledBack:
      'Setup cannot finish yet: the {{place}} page is no longer done — another tab changed it, or one of its checks turned red. Finish this page first, then go on to the end.',
    fixTmdb: 'Go back and enter the TMDB key',
    signInHint:
      'You go straight into Berth. Signing in always uses a Jellyfin account from now on: you are {{name}}, everyone else uses their own Jellyfin account, and only its administrators reach the settings.',
    savePath: 'Complete directory',
    skippedTitle: 'Skipped steps',
    cutaway: {
      title: 'What this run produced',
      routes: 'Routes',
      skipped: 'Skipped',
      nothing: 'Nothing',
    },
    skipped: {
      indexers: 'Prowlarr',
    },
    where: {
      indexers:
        'Prowlarr is not connected yet. Connect it later under Settings → Prowlarr; until then searches return nothing.',
      indexersPresent_one:
        'Skipped, but Prowlarr already has {{count}} site, and searches use it. Add sites and try searches under Settings → Prowlarr.',
      indexersPresent_other:
        'Skipped, but Prowlarr already has {{count}} sites, and searches use them. Add sites and try searches under Settings → Prowlarr.',
      indexersUnread:
        'Skipped, and Prowlarr’s site list could not be read this time. Check or add sites later under Settings → Prowlarr.',
    },
  },
  login: {
    code: 'BTH 0',
    title: 'Gangway',
    field: {
      username: 'Jellyfin username',
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
    rss: 'RSS',
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
    downloads: {
      title: 'Downloads',
      filters: 'Filter this title’s downloads',
      filter: {
        open_one: 'Open {{count}}',
        open_other: 'Open {{count}}',
        all_one: 'All {{count}}',
        all_other: 'All {{count}}',
      },
      pages: 'Download pages',
      pagesEnd: 'Download pages, end of list',
      noneOpen: 'Nothing for this title is on its way or waiting for you to confirm.',
      off: 'Can’t read this title’s downloads. Berth’s own API isn’t answering — check that it is still running.',
      retry: 'Retry',
      files: {
        title: 'Files',
        loading: 'Reading the file list…',
        none: 'qBittorrent hasn’t listed this torrent’s files yet.',
        off: 'Can’t read the file list. Berth’s own API isn’t answering.',
        unwanted: 'Not downloaded',
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
        searching: 'Jellyfin is still scanning; Berth checks again',
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
    indexers: 'the indexer',
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
    onlyAside_one:
      "The {{count}} release carrying this title's name has the wrong year or type; it is set aside below. Try typing a keyword.",
    onlyAside_other:
      "All {{count}} releases carrying this title's name have the wrong year or type; they are set aside below. Try typing a keyword.",
    setAside_one:
      '{{count}} more release has the wrong year or type for this title and was set aside.',
    setAside_other:
      '{{count}} more releases have the wrong year or type for this title and were set aside.',
    off: "The search never went out. Berth's own API did not answer; check that it is still running.",
    announce_one: 'Found {{count}} result; {{failed}} keywords went unanswered.',
    announce_other: 'Found {{count}} results; {{failed}} keywords went unanswered.',
    column: {
      title: 'Release',
      size: 'Size',
      seeders: 'Seeders',
      indexer: 'Source',
      estimate: 'Estimate',
      published: 'Published',
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
    batch: {
      preview: 'Asked in batches: this batch asks for {{seasons}}.',
      laterPreview: ' {{later}} more to go after it.',
      asked: 'This batch asked for {{seasons}}.',
      next: ' {{later}} more to go; the next asks for {{seasons}}.',
      last: ' This was the last batch.',
      pending: 'This batch asks for {{seasons}}; nothing has been asked yet.',
      ask: 'Ask the next batch',
      wait: 'The request budget has room for it again:',
      join: ', ',
    },
    problem: {
      not_configured: {
        label: 'Not connected',
        body: 'Step 6 of the setup wizard skipped Prowlarr, so Berth has nowhere to search. Connect Prowlarr and this section comes alive.',
      },
      no_query: {
        label: 'Nothing to ask',
        body: 'Berth has no TMDB snapshot for this title yet, so it does not know what names to ask for. Hit Refresh now above, or type a keyword yourself.',
      },
      credential_rejected: {
        label: 'Credential rejected',
        body: 'The indexer rejected this API key. It may have been rotated, or lost a few characters on the way in.',
      },
      unreachable: {
        label: 'Unreachable',
        body: 'Cannot reach the indexer. Either its container is not running, or the address is wrong.',
      },
      budget_exhausted: {
        label: 'Waiting for the budget',
        body: "This hour's request budget for the sites behind the indexer can't fit this batch, so not a single keyword was asked. RSS polling, the daily backfill and search share it, so Berth doesn't get your IP banned from public sites.",
      },
      retryAt: 'It fits again:',
      askAdmin: 'Ask an administrator to connect an indexer in Settings.',
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
    differs: 'What differs',
    differsJoin: ', ',
    differsWhat: { season: 'season', episode: 'episode', tmdb: 'title' },
    ledgerReads: 'Ledger',
    jellyfinReads: 'Jellyfin reads',
    noTmdb: 'no TMDB id',
    nextMismatch:
      'Fix it in Jellyfin: if it matched the wrong title, use Identify to pick the one the ledger has; if two files covering different episodes were merged into one, move one of them out. Then press Look it up again; the next reconcile also closes this on its own once they agree.',
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
      jellyfin_item_mismatch: 'Jellyfin reads a different episode or title than the ledger',
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
      jellyfin_item_mismatch: 'JELLYFIN DISAGREES',
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
        air_date_conflict:
          'The release date does not fit the air date of the episode it was mapped to; the episode is likely wrong',
        runtime_conflict:
          'The measured runtime is far from TMDB’s for that episode; likely a special or a merged file taken for an episode',
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
      unapplied:
        'Some changes aren’t applied yet — press “{{apply}}” or “{{cancel}}” first: {{files}}',
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
        not_from_series:
          'This plan was not sent by an RSS Series, so there is no Series to apply to. Untick “Apply to this RSS Series” and try again:',
        no_episode_number:
          'The file name carries no episode number, so no offset can be worked out. Untick “Apply to this RSS Series” to change only this row:',
      },
      stillToApprove: 'This plan keeps your change and imports once you approve it.',
    },
    audit: {
      label: 'UNCONFIRMED',
      reason: {
        medium_auto_imported: 'Medium confidence, imported automatically',
        first_batch: 'First batch of an RSS Series: check the season and episode numbers',
      },
      because: 'Medium confidence: {{lead}}',
      lead: {
        title_mismatch: 'the release title does not look like this title',
        strategy_outlier: 'the rest of this batch was read by {{strategy}}, this one was not',
        single_season: 'the season was inferred (TMDB has only one season)',
        season_from_arc: 'the season was inferred from an arc name',
        final_season: 'the season was inferred (“final season” taken as the last one)',
        air_date_run: 'the season was worked out by splitting air dates into runs',
        published_in_run: 'the season was inferred from the run on air when it was released',
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
      series: {
        firstBatch_one:
          'First batch of an RSS Series: {{count}} file waiting for a look at its season and episode',
        firstBatch_other:
          'First batch of an RSS Series: {{count}} files waiting for a look at their seasons and episodes',
        name: 'RSS Series',
        values: 'Season and offset',
        unset: 'Not set; the parser decides',
      },
      confirmAll: 'Confirm all',
      confirmSeries: 'Confirm the whole Series',
      confirmSection_one:
        'The {{count}} imported file listed in this section is marked as right; no file is touched. Anything that arrives after you press this is not included.',
      confirmSection_other:
        'The {{count}} imported files listed in this section are marked as right; no file is touched. Anything that arrives after you press this is not included.',
      confirmSectionSeries_one:
        'This also confirms the first batch of {{count}} RSS Series; its later medium imports no longer come here.',
      confirmSectionSeries_other:
        'This also confirms the first batch of {{count}} RSS Series; their later medium imports no longer come here.',
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
      correct: 'Fix episode',
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
    confirmMoveSeries:
      'The file leaves its current place in the library and moves to the new one, and the other unconfirmed episodes of this RSS Series move by the new season and offset. Nothing under complete is touched.',
    confirmAction: 'Apply the fix',
    done: 'Fixed.',
    applyToSeries: 'Apply to this RSS Series',
    applyToSeriesHint:
      'Writes the season and episode offset back and works out the Series’ unconfirmed episodes again.',
    series: {
      set: 'Fixed; this RSS Series now uses {{values}}.',
      moved_one: 'One other episode followed.',
      moved_other: 'The other {{count}} episodes followed.',
      replanned_one: '{{count}} download waiting for review was planned again with the new values.',
      replanned_other:
        '{{count}} downloads waiting for review were planned again with the new values.',
      left_one: '{{count}} episode could not be moved and stays where it is for you to check.',
      left_other: '{{count}} episodes could not be moved and stay where they are for you to check.',
      nothingElse: 'No other unconfirmed episodes needed to follow.',
    },
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
      not_from_series:
        'This file was not sent by an RSS Series, so there is no Series to apply to. Untick “Apply to this RSS Series” and try again:',
      no_episode_number:
        'The file name carries no episode number, so no offset can be worked out. Untick “Apply to this RSS Series” to fix only this episode:',
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
    filters: 'Download filters',
    filter: {
      active_one: 'On the way {{count}}',
      active_other: 'On the way {{count}}',
      attention_one: 'Needs you {{count}}',
      attention_other: 'Needs you {{count}}',
      imported_one: 'Imported {{count}}',
      imported_other: 'Imported {{count}}',
      all_one: 'All {{count}}',
      all_other: 'All {{count}}',
    },
    pages: 'Pages',
    pagesEnd: 'Pages, end of list',
    range: 'Jobs {{first}}–{{last}} of {{total}}',
    rangeBeyond: 'This page is past the end; {{total}} jobs in all',
    emptyFilter: {
      active: 'Nothing on the way: everything sent has been imported or removed.',
      attention: 'Nothing needs you.',
      imported: 'Nothing has been imported yet.',
    },
    toFilter: {
      active: 'Show what is on the way',
      imported: 'Show imported',
    },
    emptyPage: 'Nothing on this page: the list got shorter while you were paging.',
    toFirstPage: 'Back to the first page',
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
      series_confirmed: 'Series confirmed by Berth',
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
      resendAt: 'Attempt {{attempt}} did not go through; sending again automatically',
      resendSpent:
        'Tried {{attempt}} times without success; no more automatic tries. Retry once it is fixed.',
      linkedFiles_one: '{{count}} file',
      linkedFiles_other: '{{count}} files',
      linkedTargets: 'List the targets',
      scanRequested_one: 'told about {{count}} file path',
      scanRequested_other: 'told about {{count}} file paths',
      resolved_one: 'found {{count}} file in Jellyfin',
      resolved_other: 'found {{count}} files in Jellyfin',
      grounds: 'Bound automatically, because:',
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
        air_date_conflict: 'the release date does not fit the air date',
        runtime_conflict: 'the runtime does not fit TMDB’s episode',
      },
      reviewApproved_one: 'An administrator approved it; {{count}} file will be imported',
      reviewApproved_other: 'An administrator approved it; {{count}} files will be imported',
      reviewRejected: 'An administrator rejected this plan; Berth plans it again',
      auditConfirmed: 'An administrator looked at this medium-confidence import and confirmed it',
      seriesConfirmed:
        'The first batch was strong enough evidence, so Berth confirmed this RSS Series: every episode maps straight from the number in its file name, had just aired when it was released, and matches its air date. Later episodes import on the usual confidence rules.',
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
        round_failed: 'The error from the last round did not come back; this round went through.',
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
      series: 'Per the RSS Series: {{values}}',
      seriesUnset: 'The RSS Series sets no season or episode offset; the parser decided',
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
        air_date_conflict:
          'A file’s release date does not fit the air date of the episode it was mapped to: it came out before that episode aired, or far behind the episode this title is airing now. The season, offset or absolute numbering is most likely wrong. An administrator corrects each row’s episode in the review queue; if it is actually right, such as a BD release months later, approving imports it where shown.',
        runtime_conflict:
          'A file’s measured runtime is far from TMDB’s runtime for the episode it was mapped to: most likely a special, an OVA or two episodes in one file was taken for a single episode. An administrator changes that row to an extra, unmatched or the right episode in the review queue; if the runtime is actually fine (a wrong TMDB entry, a different cut), approving imports it where shown.',
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
        published_in_run:
          'Only an episode number; released on {{published}}, when run {{run}} of {{runs}} was on air (it starts at {{episode}}), so the number counts from 01 within that run',
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
        released_before_airing:
          'released on {{published}}, more than two days before TMDB’s air date for {{episode}} ({{aired}}): the episode was most likely worked out wrong',
        behind_latest_episode:
          '{{episode}} aired on {{aired}}, but when this came out the title’s latest episode was {{latest}} ({{latest_aired}}): the season or offset is most likely wrong',
        air_date_missing:
          'TMDB has no air date for {{episode}}, so the release date was not checked',
        published_missing: 'the source gave no release date, so the air date was not checked',
        runtime_mismatch:
          'mediainfo measured {{measured}}, but TMDB lists {{episode}} at {{minutes}} min: too far off, most likely a special, an OVA or two episodes in one file',
        runtime_missing: 'TMDB has no runtime for {{episode}}, so the runtime was not checked',
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
        series_corrected:
          'Worked out again after another episode of this RSS Series was fixed: season {{season}}, episode offset {{offset}}',
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
        published_run: 'the release date',
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
        'Berth has no TMDB credential. It ships without one: get your own key at themoviedb.org and paste it under Settings → TMDB.',
      credential_rejected:
        'TMDB rejected this credential. It may have been revoked, or lost a few characters on the way in.',
      unreachable:
        'Cannot reach TMDB. Either this machine has no outbound network, or TMDB is down.',
      not_found:
        'TMDB has no such title. It may have been merged or removed — go back to Discover and look it up again.',
      askAdmin: 'Ask an administrator to add the TMDB credential in Settings.',
      retry: 'Retry',
    },
  },
  health: {
    title: 'Health',
    failedLine:
      'This round’s health check did not pass: {{service}} did not answer, or answered with an error.',
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
    // Jellyfin only: library count (ticket 21). No other service has this number.
    libraryCount_one: '{{count}} library',
    libraryCount_other: '{{count}} libraries',
    state: {
      ok: 'Ready',
      failed: 'Blocked',
      unknown: 'Not checked',
      unconfigured: 'Not connected',
    },
    budget: {
      title: 'Request budget',
      help: "At most {{limit}} requests per site per hour. RSS polling, the daily backfill and search share it, so Berth doesn't get your IP banned from public sites. Restarting Berth resets it.",
      idle: 'No site has been asked this hour.',
      useCount: '{{use}} {{value}}',
      use: {
        poll: 'RSS polling',
        backfill: 'Daily backfill',
        search: 'Search',
        manual: 'Manual reads',
      },
      deferred: 'Deferred: {{use}} ({{value}} requests held back)',
      until: 'Fits again:',
      never: 'It asks for more than the whole budget, so it never fits.',
    },
    poller: {
      title: 'Download loop',
      lastRound: 'Last poll',
      every: 'every {{seconds}}s while downloading',
      failures: 'Consecutive failures',
      error: 'Last error',
      errorLine: 'The last round asking qBittorrent failed.',
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
        'No routes yet. Add one under Settings → Library paths — until then Berth has nowhere to write.',
    },
    fix: {
      title: 'Fix',
      banned:
        'qBittorrent has banned this machine after repeated failed logins. **Changing the password will not help** — it only fails a few more times and restarts the ban. The ban is on the source IP qBittorrent sees: when Berth reaches it through a host port or host.docker.internal, that is usually your browser’s source too, so its WebUI will refuse you from the host for the same time. Wait for it to expire (1 hour by default), clear the ban in qBittorrent, or restart its container: the ban lives in memory only. Once the credentials are right, Berth turns green again on its next round.',
      bundled:
        'This service comes from the bundled compose file, so start by checking that its container is still running. The three commands are in triage order: is it there, bring it up, what did it say.',
      existing:
        'This is your own service, and all Berth knows is that it stopped answering. If its address or credentials changed, fill them in again on its settings page.',
      unconfigured:
        'This service is not connected yet. Connect it on its settings page — until then, whatever it is responsible for simply will not happen.',
      askAdmin: 'Only administrators can open Settings — ask one to take a look.',
      unsupported:
        'Berth needs Jellyfin 12.0 or newer (12.0 is what would have been 10.12). Before upgrading, back up Jellyfin’s /config in full — 12 changes the database and there is no way back — and remove third-party plugins, which cannot load on 12. Run one full library scan afterwards.',
    },
  },
  settings: {
    go: 'Open {{place}} settings',
    check: 'Check again',
    checking: 'Checking…',
    checkFailed:
      'The check did not go through. The Berth backend may be down — check the container, then try again.',
    health: 'Health',
    tabs: {
      label: 'Settings',
    },
    connection: {
      title: 'Address and credentials',
      lede: 'The same block as the top of that wizard page: submitting saves it, then really connects once. The card above checks again right after.',
      locked:
        'The owner is an account on this Jellyfin, so its source cannot change; if the same Jellyfin moved to a new address, change it here — another server is refused.',
    },
    jellyfinPage: {
      title: 'Jellyfin settings',
      lede: 'Whether this Jellyfin still answers, whether its address or API key needs changing, and where “Open in Jellyfin” on the library page opens.',
      signIn: {
        title: 'Administrator sign-in',
        lede: 'Berth talks to Jellyfin with an API key of its own. If that key was revoked, sign in as an administrator once more to get a new one.',
      },
    },
    qbittorrentPage: {
      title: 'qBittorrent settings',
      lede: 'Whether this qBittorrent still answers, whether its address or credentials need changing, and how little free disk space stops new downloads.',
    },
    indexerPage: {
      sites: 'Sites',
      title: 'Prowlarr settings',
      lede: 'Add sites, try a search, remove what you do not want; when you run your own Prowlarr, change its address or key here.',
    },
    tmdbPage: {
      title: 'TMDB settings',
      lede: 'Swap in another TMDB API key. The new key replaces the old one only once it passes the test; if it fails, the old key stays in use and browsing and imports carry on.',
      kept: 'This key failed the test and was not saved — browsing and imports keep using the one you had.',
      failed:
        'The test did not go through. The Berth backend may be down — check the container, then try again.',
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
  },
  routeSettings: {
    title: 'Routes',
    lede: 'Each route is one Jellyfin library plus one write target, and a library can have several — one per disk, say. A disabled route takes no new downloads; a route that downloads or imported files still point at cannot be deleted.',
    empty: 'No routes yet. Create one with “Add route” below, so Berth has somewhere to write.',
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
        'A disabled route takes no new downloads; the ones already on their way still import. Enabling it runs every check again first.',
      identity:
        'The slug and the write target cannot change once the route exists: the category, the complete subdirectory and the ledger all go by them. To use another target, add a route and delete this one.',
      save: 'Save',
      saveRechecks:
        'Saving runs every check below again: that round creates the qBittorrent category and writes a probe file into the write target.',
      saving: 'Saving and checking…',
      saved: 'Saved.',
      unhealthy:
        'Not every check passed, so this route stays disabled. Fix the red one below and press Save again.',
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
      createdOk: 'Created “{{name}}”: every check passed and it is enabled.',
      createdRed:
        'Created “{{name}}”, but not every check passed, so it stays disabled. Fix the mount, check it again in its row, then tick Enabled.',
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
  rss: {
    title: 'RSS',
    off: "Can't read the RSS lists. Berth's own API isn't answering — check that it's still running.",
    values: {
      both: 'season {{season}}, episode offset {{offset}}',
      season: 'season {{season}}, no episode offset',
      offset: 'episode offset {{offset}}, season left to the parser',
    },
    firstBatch: {
      ask: 'Check how {{title}} × {{group}} maps to seasons: {{episodes}} {{basis}}',
      askUngrouped: 'Check how {{title}} maps to seasons: {{episodes}} {{basis}}',
      separator: ', ',
      basis: {
        literal: 'read straight from the episode numbers',
        series: 'from the season and offset set on the Series',
        absolute: 'converted from absolute episode numbers',
        runs: 'counted within a later run (the group restarted at 01)',
        arc: 'season read from the arc name',
        mixed: 'read more than one way',
      },
    },
    failed:
      "That didn't go through. Reload the page and try again; if it still fails, look at the health page.",
    kind: { mikan: 'MIKAN', nyaa: 'NYAA', acgrip: 'ACG.RIP' },
    // The detail page's RSS subscription (M3 ticket 19, `media/SubscribePanel.tsx`).
    subscribe: {
      title: 'RSS subscriptions',
      toRss: 'Go to RSS',
      none: 'No RSS series is bound to this title yet.',
      confirmed: 'First batch confirmed',
      firstBatch: 'First batch awaiting review',
      latest: 'Latest:',
      nothingYet: 'Nothing has come in yet.',
      start: 'Add a subscription',
      label: 'Pick a source to create a feed; every episode it brings is imported into this title.',
      source: 'Source',
      about: {
        mikan:
          'Pick a show and a fansub group; the whole season is filled in and new episodes download on their own',
        nyaa: 'Search by title; you see the first round before anything downloads',
        acgrip: 'Search by title; you see the first round before anything downloads',
      },
      mikanSearch: 'Search Mikan for the show',
      search: 'Search',
      searching: 'Searching…',
      noBangumi:
        'Mikan found no show. Try another name (Chinese, Japanese, English and romaji all work).',
      bangumi: 'Show',
      reading: 'Reading the fansub groups of this show…',
      noSubgroups: 'No fansub group has released this show yet.',
      subgroup: 'Fansub group',
      releases_one: '{{count}} release · latest {{updated}}',
      releases_other: '{{count}} releases · latest {{updated}}',
      boundHere: 'Already subscribed for this title',
      boundElsewhere: 'Already bound to another title ({{id}})',
      confirm: 'Subscribe, new episodes only',
      confirmBackfill: 'Subscribe and fill in older episodes',
      subscribing: 'Subscribing…',
      subscribed_one: 'Subscribed; sent {{count}} episode.',
      subscribed_other: 'Subscribed; sent {{count}} episodes.',
      titles: 'Names of this title',
      term: 'Search term',
      termHint: {
        mikan: '',
        nyaa: 'Berth creates a Nyaa search feed for this term (all anime categories).',
        acgrip: 'Berth creates an acg.rip search feed for this term.',
      },
      create: 'Create search feed',
      creating: 'Creating and reading the first round…',
      made: '“{{name}}” is created. Every fansub group it brings is bound to this title; look at the first round before deciding whether to download the older releases.',
      decideLater: 'Decide later on the RSS page',
      later: 'The search feed is created; its first round waits for you on the RSS page.',
      unreachable:
        'Mikan cannot be reached right now, so nothing was added. Try again shortly. Original message:',
    },
    refusal: {
      feed_missing: 'This feed is gone — another tab probably just deleted it.',
      feed_unsupported:
        "Berth doesn't recognise this address. This version takes Mikan (mikanani.me), Nyaa (nyaa.si) and acg.rip RSS addresses.",
      feed_duplicate: 'This address is already a feed.',
      series_missing: 'This RSS Series is gone. Reload the page.',
      series_bound:
        'This RSS Series is already bound — probably from another tab. Unbind it first to pick another title.',
      media_missing:
        "Can't read this title's details. Pick another, or wait for TMDB to come back.",
      route_missing: 'That route is gone.',
      route_disabled:
        'That route is disabled. Enable it under Settings → Library paths, or pick another.',
      route_kind_mismatch:
        "That route doesn't hold this kind of title (series only go into a TV library).",
      rule_invalid: 'That exclusion rule is broken; nothing was saved.',
      feed_primed: "This feed's first round has already been decided — probably from another tab.",
      feed_unreachable:
        "Can't read this feed right now, so there's no telling which items came before; nothing was changed. Try again in a moment. Original error:",
      feed_unread:
        "This feed hasn't been read yet. Press Poll now to see its first round before choosing.",
      feed_not_rss:
        "Got an answer, but it isn't RSS. This is usually a web page address: find the site's RSS link instead (the RSS icon next to a fansub on a Mikan show page, the RSS button on a Nyaa search).",
      budget_exhausted:
        "This hour's request budget for that site is used up, so nothing was sent. Try again once it has room (the health page says when). Original error:",
    },
    feeds: {
      title: 'Feeds',
      empty:
        'No feeds yet. Sign in to Mikan, subscribe to the shows and fansub groups you follow, and paste the RSS address from the My Bangumi page below.',
      add: 'Add a feed',
      url: 'RSS address',
      urlHint:
        "Mikan's My Bangumi RSS (/RSS/MyBangumi?token=…) or a single show's RSS; a Nyaa or acg.rip search RSS.",
      name: 'Name (optional)',
      nameHint: "Left blank, the address's host name is used.",
      route: 'Auto-bind into',
      routeNone: 'Not set',
      routeHint:
        'When more than one route takes a recognised title, it goes into this one. Not set, those titles wait in unbound for you to pick.',
      sendsTo: 'auto-binds into',
      addAction: 'Add',
      count_one: '{{count}} feed',
      count_other: '{{count}} feeds',
      toMikan: 'Open Mikan',
      adding: 'Adding…',
      every: 'Every {{minutes}} min',
      polled: 'Last polled',
      items_one: '{{count}} item',
      items_other: '{{count}} items',
      failed: 'Last round had problems',
      undecided:
        "The first round isn't decided yet, so nothing is sent: choose Only what comes next or Download everything at the top of the page.",
      polledFailed:
        "This round couldn't read the feed, so nothing changed. The reason is above; the next background poll tries again.",
      polledNow:
        'This round: {{items}} new items, {{series}} new RSS Series ({{bound}} bound automatically), {{sent}} sent.',
      poll: 'Poll now',
      polling: 'Polling…',
      delete: 'Delete',
      deleteConfirm: 'Delete this feed',
      deleteWarning_one:
        'Its {{count}} feed item goes with it. RSS Series and their bindings stay; add the same address back and nothing already sent is sent again.',
      deleteWarning_other:
        'Its {{count}} feed items go with it. RSS Series and their bindings stay; add the same address back and nothing already sent is sent again.',
      deleting: 'Deleting…',
    },
    pending: {
      title: 'Waiting to bind',
      chip_one: '{{count}} to bind',
      chip_other: '{{count}} to bind',
      lede: 'New title × fansub group pairs from your feeds. Bind one to a TMDB title and a route, and the episodes it has been holding are sent.',
      label: 'To bind',
      waiting_one: 'Holding {{count}} episode until it is bound',
      waiting_other: 'Holding {{count}} episodes until it is bound',
      why: 'Not bound automatically:',
    },
    bind: {
      start: 'Bind',
      label: 'Which title is this?',
      search: 'Search TMDB',
      searching: 'Searching…',
      off: "TMDB isn't returning results right now. Check the health page.",
      none: 'Nothing found. Try another name (English or original title).',
      results: 'Search results',
      reading: 'Reading this title…',
      mediaOff: "Can't read this title's details; TMDB may be unreachable.",
      willFreeze: "Binding fixes the folder name; later title changes on TMDB won't touch it:",
      alreadyFrozen: "This title's folder name is already fixed:",
      willSend_one: 'Binding sends {{count}} episode to qBittorrent.',
      willSend_other: 'Binding sends {{count}} episodes to qBittorrent.',
      confirm_one: 'Bind and send {{count}} episode',
      confirm_other: 'Bind and send {{count}} episodes',
      backfill: 'Also download earlier episodes',
      backfillOn:
        "Reads this group's whole season on Mikan and sends the episodes the feed didn't carry; ones already in the library or already downloaded are skipped. Missed episodes are picked up once a day after that.",
      backfillOff:
        'Sends only the episodes the feed carried. Earlier ones are marked as passed, and the daily catch-up will not send them either.',
      confirmBackfill_one: 'Bind, send {{count}} episode and catch up',
      confirmBackfill_other: 'Bind, send {{count}} episodes and catch up',
      binding: 'Binding…',
      kind: { tv: 'Series', movie: 'Film' },
      done_one: 'Bound. {{count}} episode sent.',
      done_other: 'Bound. {{count}} episodes sent.',
      candidates: 'Candidates',
      pick: 'Pick {{title}}',
    },
    bound: {
      title: 'RSS Series',
      count_one: '{{count}} series',
      count_other: '{{count}} series',
      route: 'Imports to {{route}}',
      season: 'Season {{season}}',
      offset: 'Episode offset {{offset}}',
      unbind: 'Unbind',
      unbindConfirm: 'Unbind',
      unbindWarning:
        'Episodes not yet sent go back to waiting; downloads already sent and the folder name stay. New episodes wait until you bind it again.',
      unbinding: 'Unbinding…',
      unbound: 'Unbound.',
      automatic: 'Bound automatically',
      grounds: 'Because:',
      imported: '{{n}} in library',
      active: '{{n}} on the way',
      excluded: '{{n}} excluded',
      latest: 'Latest {{episode}}',
      latestUnnumbered: 'Latest',
      nothingYet: 'Nothing released yet',
      finished_one: '{{count}} finished',
      finished_other: '{{count}} finished',
      finishedLede:
        'Aired out and all in the library, or nothing new for 30 days. The record stays; a new item brings it back up.',
      allFinished: 'No RSS Series is still being followed.',
      items: 'Its feed items',
      itemsLoading: 'Reading its feed items…',
      itemsOff: "Can't read its feed items.",
      itemsRetry: 'Read again',
      itemsEmpty: 'Its feed items went with the feed that was deleted.',
      advanced: 'Advanced',
    },
    source: {
      mikan: 'Mikan: {{bangumi}}',
      mikanGroup: 'Mikan: {{bangumi}} × {{group}}',
      mikanBare: 'Mikan',
    },
    grounds: {
      title_equal: '“{{clue}}” has the same name as “{{title}}” on TMDB',
      premiere_near:
        'Mikan says it started on {{premiere}}; TMDB season {{season}} premiered on {{aired}}',
      release_near: 'Mikan says {{premiere}}; TMDB has it released on {{aired}}',
      season_airing:
        'the name says season {{season}}; Mikan says it started on {{premiere}}, while that season was airing on TMDB ({{episode}} aired on {{aired}})',
      only_route: 'the only route that takes it is {{route}}',
      feed_route: 'more than one route takes it; this feed sends to {{route}}',
      no_candidate: 'nothing on TMDB has the same name',
      premiere_far:
        '{{title}} has the same name, but none of its seasons premiered near {{premiere}} (the start date on Mikan)',
      several_candidates: '{{number}} titles have the same name and a matching start date',
      no_premiere: 'the Mikan show page has no start date, so the year cannot be checked',
      no_show_page:
        'this source has no show page, so the year cannot be checked: the candidates come from the title alone and need you to confirm',
      lookup_failed: 'the Mikan show page or TMDB could not be read ({{detail}}); bind it yourself',
      lookup_deferred:
        'the request budget for {{site}} is used up for this hour; the show page is read next round',
      lookup_retry:
        '{{site}} could not be read this time ({{detail}}); looking it up again at {{at}} (retry {{attempt}})',
      route_ambiguous: 'the title was recognised, but {{routes}} can all take it',
      no_route: 'the title was recognised, but no enabled route takes it',
    },
    first: {
      title: 'Your call: first round of a new feed',
      chip_one: '{{count}} to decide',
      chip_other: '{{count}} to decide',
      lede: 'A search feed brings months of history in its first round. Until you choose, nothing from this feed is sent.',
      unread:
        "The first round hasn't run yet: the background poll reads it within half a minute, or press Poll now in the Feeds section below. Every item shows up here once it's read.",
      unreadFailed:
        'Nothing has been read from it yet, so there is nothing to choose. The next background poll tries again, or press Poll now in the Feeds section below. Last time:',
      tally: {
        send_one: '{{count}} to send',
        send_other: '{{count}} to send',
        bind_one: '{{count}} after binding',
        bind_other: '{{count}} after binding',
        excluded_one: '{{count}} excluded',
        excluded_other: '{{count}} excluded',
        duplicate_one: '{{count}} duplicate',
        duplicate_other: '{{count}} duplicates',
      },
      group: {
        send_one: 'To send ({{count}} item)',
        send_other: 'To send ({{count}} items)',
        bind_one: 'Sent after binding ({{count}} item)',
        bind_other: 'Sent after binding ({{count}} items)',
        excluded_one: 'Excluded ({{count}} item)',
        excluded_other: 'Excluded ({{count}} items)',
        duplicate_one: 'Duplicate ({{count}} item)',
        duplicate_other: 'Duplicates ({{count}} items)',
      },
      show: 'Show {{name}}',
      bindHint: 'Their RSS Series wait in the To bind section below; they are sent once bound.',
      later: 'Only what comes next',
      laterHint:
        'Only what comes next reads the feed once more right now and passes over everything already in it; items that show up later are sent as usual. The choice is final: to start over, delete the feed and add it again.',
      all: 'Download everything',
      allConfirm: 'Download everything',
      allWarning:
        'Sends {{send}} items to qBittorrent now; {{bind}} more are sent once their RSS Series are bound. Excluded and duplicate items are not sent.',
      priming: 'Deciding…',
      donePassed_one: '{{name}}: only what comes next, {{count}} item passed over.',
      donePassed_other: '{{name}}: only what comes next, {{count}} items passed over.',
      doneSent_one: '{{name}}: download everything, {{count}} item sent.',
      doneSent_other: '{{name}}: download everything, {{count}} items sent.',
    },
    oneshot: {
      title: 'One-off RSS link',
      lede: "Paste an RSS address, read it once and send the items you tick. No feed is created, so later episodes won't download on their own. Exclusions only apply to automatic downloads, so they don't block anything here: batches can be ticked too.",
      url: 'Address to read',
      urlHint:
        'A Mikan single-show RSS (/RSS/Bangumi?bangumiId=…), or a Nyaa or acg.rip search RSS.',
      read: 'Read',
      reading: 'Reading…',
      unreachable:
        "Can't read this address right now. Press Read again in a moment. The original error is below.",
      empty: 'This feed has no items.',
      count_one: '{{count}} item read',
      count_other: '{{count}} items read',
      work: 'Send to which title',
      list: 'Tick what to send',
      pickAll_one: 'Tick every single episode ({{count}})',
      pickAll_other: 'Tick every single episode ({{count}})',
      pickNone: 'Untick all',
      kind: { range: 'Range', batch: 'Season pack', collection: 'Batch' },
      hasJob: 'This one is already downloading or downloaded.',
      known: 'The library already has this version: {{known}}',
      needWork:
        'Pick a title and a route to send. Once picked, the list maps episodes against that title and marks what the library already has.',
      willFreeze:
        "The folder name is fixed the first time something is sent, and later TMDB title changes won't touch it:",
      pickFirst: 'Tick something to send',
      send_one: 'Send {{count}} item',
      send_other: 'Send {{count}} items',
      sending: 'Sending… {{done}}/{{total}}',
      stopped:
        "Stopped part way ({{done}} handled): Berth didn't answer. The ones not sent are still ticked; try again in a moment.",
      done: '{{sent}} sent; {{already}} already there; {{refused}} not sent.',
      outcome: { sent: 'Sent', already: 'Already there' },
    },
    series: {
      page: 'Mikan show page',
    },
    rules: {
      title: 'Exclusions',
      lede: 'Everything in a feed is downloaded unless a rule here blocks it. Global, feed and RSS Series rules add up: a rule blocks on whichever level it sits. Changes only reach items not sent yet; removing a rule does not bring back what it already blocked.',
      notSingle:
        "Don't download batches automatically (anything but a single episode: batches, ranges, season packs)",
      notSingleHint: 'Batches can still be sent by hand from search or a one-off RSS link.',
      none: 'No exclusions.',
      list: 'Exclusions',
      add: 'Add an exclusion',
      hint: 'Plain words match anywhere in the title, ignoring case; wrap in /…/ for a regex (/…/i ignores case).',
      addAction: 'Add rule',
      saving: 'Saving…',
      remove: 'Remove “{{rule}}”',
      suggestions: 'Suggestions',
      suggest: 'Add “{{rule}}”',
      invalid: 'Not saved: {{detail}}',
      toggle_one: 'Exclusions ({{count}})',
      toggle_other: 'Exclusions ({{count}})',
      feedLede: 'For this feed only, on top of the global rules.',
      seriesLede: 'For this RSS Series only, on top of the global and feed rules.',
    },
    skip: {
      not_single:
        'Not a single episode (a batch, range or season pack), so not downloaded automatically',
      global_rule: 'Blocked by the global rule “{{rule}}”',
      feed_rule: 'Blocked by this feed’s rule “{{rule}}”',
      series_rule: 'Blocked by this RSS Series’ rule “{{rule}}”',
      same_torrent: 'The same torrent was already sent (from another feed or by hand)',
      in_library: 'The library already has this version: {{known}}',
    },
    items: {
      title: 'Recent feed items',
      count_one: '{{count}} item',
      count_other: '{{count}} items',
      empty: 'No feed items yet. Add a feed and press Poll now.',
      published: 'Published',
      job: 'Open this download',
      from: 'From',
      work: '{{work}} × {{group}}',
      unbound: 'Not bound yet',
      status: {
        unbound: 'To bind',
        matched: 'To send',
        downloaded: 'Sent',
        stuck: "Can't send",
        excluded: 'Excluded',
        duplicate: 'Duplicate',
        passed: 'Passed over',
      },
      passed:
        'The feed was new and you chose to follow only what comes next: this item was already in it.',
    },
  },
  pager: {
    previous: 'Previous',
    next: 'Next',
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

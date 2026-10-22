# 133 — M4 驗收

**Status:** done

**Blocked by:** 121、122、123、124、125、126、127、128、129、130、131、132

**讀:** plan §11.5 的驗收段、§10；`docs/development.md`〈e2e〉；`tests/e2e/`（`conftest.py`、`test_4_m3_rss.py`、`stack.py`）；票 123 的 Discord base URL 環境變數；M3 票 21（上一個里程碑的驗收怎麼做）

## 為什麼

plan §11.5 的驗收要在真的 qBittorrent 與 Jellyfin 上走一遍；Discord 這一端用假伺服器記下收到的訊息，讓 CI 每天都能跑。

## 做什麼

1. e2e 加一個假的 Discord API（錄下每一則私訊；可以切成回 5xx 或整個關掉），Berth 用票 123 的環境變數指過去。
2. 新的 e2e 模組照 plan §11.5 的驗收：
   - RSS 命中 → 下載 → 入庫 → Jellyfin 可見：收件人收到「正在下載」與「可以看了」兩則，內容說得出作品、季集與 Route。
   - 一件進審核的事推出「等你處理」，連結開得到那一件。
   - 週報（觸發一次產生）說得出這週入庫、修了什麼、還有什麼等人。
   - 假 Discord 關掉時管線照樣走完、健康頁通知卡說得出來；打開之後補送。
3. 過一遍 121–132 的 Comments，未處理的照 M3 票 21 的做法分類歸屬，寫進 plan。
4. 使用者在試跑環境用真的 Discord 實走一次（手動，記在 Comments）。

## 驗收

- [x] 新 e2e 模組在本機 `tests.e2e.stack` 與 CI 的 e2e workflow 都綠（本機 28 passed；CI 見 Comments）
- [x] 上面四個情境各有斷言
- [x] 121–132 的 Comments 都有歸屬，寫進 plan §11.5
- [x] 使用者真機實走一次，記在 Comments
- [x] 全部檢查、pytest、vitest 綠；progress.md 的 M4 列標「驗收完成」；CHANGELOG 已更新

## Comments

### 開工時拍板的（2026-10-22）

- **週報「觸發一次產生」**：e2e 在 Berth 的容器裡直接呼叫 `compose_weekly(ends_at=local_now())`（協調者選定，選項還有測試用入口、假時鐘、環境變數）。產品不加「現在產生一份」：`week_of` 唯一，當週凍成半週、下週一的排程就跳過。寫進 plan §11.5〈M4 驗收〉。
- **票 129 的三種停住狀態**（重試用完或永久失敗的 `submit_failed`、`import_failed`、`stalled` 沒有 Issue、不進「等你處理」）：列成「待使用者決定」，沒有實作。

### e2e（`tests/e2e/test_5_m4_notify.py`，四條驗收）

假 Discord 是 compose 裡的 `discord` 容器（`tests/e2e/discord.py`，只用標準庫）：回 bot 身分、開 DM channel（id 是 `dm-<收件人>`，重啟後照樣認得）、記下每一則私訊（自己的 volume）；`mode` 檔寫 `5xx` 時全部回 503，整個關掉是 `docker stop`。Berth 由 `DISCORD_API_URL` 指過去。收件人兩位：管理員（中文、四種）與一般使用者 `bosun`（英文、Jellyfin 只開 Anime、只訂「正在下載」與「可以看了」）——每一輪由管理員按立即輪詢，他自己收不到「正在下載」（`presser`，票 126）。接著 M3 的替身站輪次往下走：第 3 輪《与你相恋》第 6 集（確認過、直接入庫）與 Re:ZERO 第 5 集（入庫進 audit），第 4 輪第 7 集在 Discord 關掉時入庫。`sites.py` 加了這三筆（TMDB 285574 的播出日：2026-07-07 起每週二）。

本機 `uv run --env-file .env python -m tests.e2e.stack` 跑了三輪，第三輪 **28 passed in 2728.65s**（約 45 分鐘，加上 build 與起停約 50 分鐘）。前兩輪紅都是測試自己的錯：

1. 第二位收件人原本叫 `deckhand`——`test_2_` 建過同名的 Jellyfin 帳號、最後停用，Jellyfin 回 400。改名 `bosun`。
2. 「等你處理」連到清單頁而不是那一件：`test_4_` 最後一條開的 Issue 在管理員訂閱前兩秒出現，看守把它當新的一件，第 3 輪的審核項在 10 分鐘合併窗裡併進同一則（「新增 2 件」）。Berth 照設計；測試改成管理員先訂其他三種、等看守三輪（30 秒）記下現在等著的，再加訂「等你處理」。

CI：workflow 的 `timeout-minutes` 60 → 90（本機一輪約 50 分鐘）。CI（2026-10-23，協調者 push 與 merge 之後）：main `0135fca7` 上 `ci.yml`（[run 39857272808](https://github.com/1morr/Berth/actions/runs/39857272808)）綠；手動觸發 `e2e.yml`（[run 39857279844](https://github.com/1morr/Berth/actions/runs/39857279844)）**28 passed in 2072.69s（34:32）**，`test_5_m4_notify` 四條全過。

斷言的界線（審查提出）：「連結開得到那一件」——e2e 斷言錨點是 `/review#{kind}-{ref}`、照連結開得到頁面（200 HTML，SPA 對任何路徑都回同一個殼）、那一列在 API 的佇列上；前端照錨點找到那一列由 `web/src/components/useHashTarget.test.tsx` 守。「健康頁說得出來」斷言的是 `/health/detail` 的 `notify`（通知卡讀的就是它），卡片文案由 `web/src/health/NotifyCard.test.tsx` 守。5xx 只對「測試」鍵驗；管線的補送驗的是整個關掉那一種。

### 使用者真機實走（2026-10-22，真的 Discord）

在 `tests/e2e/compose.yml` 那一套（本分支 build 的 Berth，不是 berth-local）上疊一份不 commit 的覆寫，把 `DISCORD_API_URL` 指回 `https://discord.com/api/v10`；精靈由 `configured` fixture 走完。使用者自己在 UI 貼 bot token（票 121 的 `berth-exp-121`，token 沒經過對話）、Berth 的網址 `http://192.168.50.76:28383`、自己的 Discord ID、介面語言繁中、四種都訂，按「測試」收到測試訊息。「正在下載」第 2 步漏勾、加 Feed 之前補勾——補勾時 Feed 0 個、Job 0 筆、待送表是空的，沒有錯過。

13:33:30Z 加兩個 Feed、**不按立即輪詢**（這一輪沒有 `presser`，管理員自己也收得到「正在下載」）：Mikan 聚合 feed（自動綁定送進 Anime，補舊集）與 Re:ZERO 的 acg.rip 搜尋 feed（長出待綁定的 Series 2）。背景輪詢 13:33:47 讀到，放位元組、recheck，四集入庫、Jellyfin 全部認出；13:45:02Z 以 `docker exec berth-e2e` 呼叫 `compose_weekly` 產生週報 1。

| # | 種類 | 送出（UTC） | 標題 | 連結 |
|---|---|---|---|---|
| 2 | 正在下載 | 13:34:01，一次 | 正在下載：與妳相戀到生命盡頭 | `http://192.168.50.76:28383/media/tv:285574` |
| 3 | 可以看了 | 13:40:47，第二次 | 可以看了：與妳相戀到生命盡頭 | `http://192.168.50.76:28383/media/tv:285574` |
| 1 | 等你處理 | 13:43:51，一次 | 有 1 件等你處理 | `http://192.168.50.76:28383/rss#series-2` |
| 4 | 週報 | 13:45:12，一次 | 週報：10-15 – 10-21 | `http://192.168.50.76:28383/weekly/1` |

使用者回報（Discord 桌面版截圖）：四則加測試訊息共五則全到，內容與預期一致——兩則 S01E01–E04、Route Anime、「在 Berth 打開」；「新增 1 件：1 個 RSS Series 待綁定」、欄位「待綁定 1」；「入庫 1 部（4 集）· 修了 0 件 · 等你處理 1 件」、「打開週報」。

**連結的驗證依據**：Discord 的 payload 不寫 log，待送表存的是事實。拆環境之前在容器裡拿待送表那四列、用送出時同一組函式（`notify._render` / `_render_waiting` / `_render_weekly` 與 `adapters/notify/discord._payload`）、存著的 Berth 網址重組一次，上表的標題與連結就是重組的結果。前兩則與週報只看存著的事實，重組與送出時相同；「等你處理」還看現在等著的，重組時是 `['rss:2']`，送出之後沒有任何操作，與送出時相同。三條連結從區網 IP 打開都是 200。

實走看到的三件事：

- **「可以看了」第一次送出失敗**：13:40 `unavailable: POST /users/@me/channels: TLS handshake got no answer`（這台機器到 discord.com 的連線瞬斷），30 秒退避後送出，健康頁失敗數歸零——真機走到了退避重送。
- **「等你處理」那一波記了三件**（`rss:1`、`review:audit:1`、`rss:2`）：《与你相恋》的 Series 長出來到自動綁定之間、第一批入庫到系統確認之間各被看守看見一次。送出時重算只說還在的那一件（`_render_waiting`），使用者收到「新增 1 件」，照設計。
- **週報標題的最後一天比入庫早一天**：標題 10-15 – 10-21，那 4 集是 10-22 入庫的。`last_day` 是 `week_of` 加 6 天，假設 `ends_at` 落在午夜；手動觸發傳的是 13:45，範圍其實到 10-22 13:45。排程的 `week_ending` 落在午夜，碰不到；只有 e2e 這種手動觸發會出現。不改（產品沒有手動觸發的入口）。

### code review（`d78f168b`，Standards 與 Spec 兩軸）

改掉的：`_digest` 改 `_info_hash`（與 CONTEXT.md「摘要」撞名）、URL 片段的 `row` 改 `fragment`、`5xx` / `ok` 收成 `discord.BROKEN` / `HEALTHY`、刪掉註解裡斷言沒驗的「其他 Job 也沒卡住」、「健康頁的通知卡」的說法改成實際斷言的 `/health/detail`；Spec 軸點出 plan §11.5「不做」兜底接住的六條（132 的週報 P2 與通知設定 P3、129 列上沒有審核頁連結、128 的 `text-blocked-ink` 與寫死的「24 小時」、122 與 127 的兩個測試缺口）逐條移進「不排里程碑」。這幾處只改名、常量與註解，沒有重跑 e2e（ruff、mypy、`test_e2e_stack` 綠）。

留著的（判斷題）：`set_round` 與 `discord_mode` 同形（往容器裡的檔案寫一個值），兩處不抽；`_to`、`wired` 的名字；`Kimi` dataclass 與 `sites.KIMI` 同名不同義；`_extra_carrying_job` 抓不到 `extra=某個變數`（`berth/` 目前沒有這種寫法）；範圍外的 `series_review` 修正與 DESIGN.md 已記進 progress.md 偏差。

另：`tests/unit/test_e2e_stack.py` 的 `_move_every_port` 變異案例與 `test_logs.py` 一起跑時紅過一次，之後連跑 9 次都綠、重現不了，沒有動它。

### 驗證（2026-10-23）

`pre-commit run --all-files` 全過（審查修改之後再跑一次）；`uv run pytest -m "not e2e"` **4339 passed, 2 skipped, 28 deselected**（15 分 44 秒，這一次沒有 WinError 10055）；`pnpm -C web test --run` **115 檔、2183 passed**；e2e 見上。

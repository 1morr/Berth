# 75 — README 說清楚為什麼有 Berth、能做什麼；拿掉 0.2.0 zip 的升級段

**Status:** done

**Blocked by:** None — can start immediately

**讀:** README、README.zh-Hant；`docs/guide/upgrading.md`；`PRODUCT.md`；CONTEXT.md（名詞）；brief §1–§3（需求與動機，按需）

## 為什麼

- 使用者要把 Berth 寫進 CV、寄信請推薦人看（2026-10-09，趕時間）。現在 README 第一段只說 Berth 做什麼，沒說為什麼做、跟現成方案差在哪，也沒列出它實際能做的事。
- 使用者自己的動機（照這個意思寫，不要誇大）：
  - 覺得 Seerr（Jellyseerr / Overseerr）搭 Sonarr、Radarr 這一套不好用、設定複雜；
  - 而且常常 request 了，卻拿不到想要的那個版本。
  - Berth 改成讓你自己挑 release（Prowlarr 搜尋）或追 RSS。
  - 另外接了 Mikan 的 RSS，方便追當季動畫。
- 使用者決定（2026-10-09）：目前沒有真的使用者，`docs/guide/upgrading.md` 的「From 0.2.0 (the zip)」那段不需要。CHANGELOG、brief、progress、研究檔是歷史紀錄，留著。

## 做什麼

1. README 開頭（截圖之前或之後，擇一，理由寫在 Comments）加一小節 **Why Berth**，3–5 行：上面的動機，口吻平實。
   - 對 Seerr / Sonarr / Radarr 只寫「Berth 的做法不同」，不貶低；
   - 不宣稱沒驗證過的優勢。
2. 加一小節 **What it does**，條列 5–8 項，每項一行，只寫已經做好、測過的功能（對照 CHANGELOG 與 guide 核實，不確定的不寫）。候選：
   - 從作品頁搜尋 Prowlarr 並自己挑 release；
   - RSS 訂閱（Mikan、Nyaa、acg.rip），新集自動送出並入庫；
   - 從檔名判斷是哪部、哪一集（TMDB），用 Jellyfin 認得的名字硬鏈接進媒體庫，不佔兩份空間；
   - 帳本與每晚對帳；
   - 健康頁；
   - 設定精靈、套件內或接既有服務；
   - 介面 zh-Hant / en。
3. README.zh-Hant.md 同輪改，兩份標題層級與連結一致（`test_readme_docs` 守）。安裝必讀的字數上限照票 57（開頭到「精靈每頁一句話」約 700 英文字）：新加的兩節若讓它超過，就精簡別處或把 What it does 放到安裝之後，理由寫在 Comments。
4. 刪掉 `docs/guide/upgrading.md` 的「From 0.2.0 (the zip)」那段，以及指向它的連結（掃斷鏈）。
5. 不改程式。跑 pre-commit run --all-files 與文件相關測試（`test_readme_docs` 等），全 repo 斷鏈掃描 0；**不跑 pytest 全套**（只動文件）。
6. progress.md 記一行；commit。

## 驗收

- [x] README 兩份都有 Why Berth 與 What it does，內容與使用者動機一致、每一項功能都對得上 CHANGELOG 或 guide
- [x] 安裝必讀字數仍在約 700 英文字內（附計算方式與數字）
- [x] upgrading.md 沒有 0.2.0 zip 段，斷鏈 0
- [x] pre-commit 與文件測試綠；progress.md 已記

## Comments

### 放在哪裡、為什麼（2026-10-09）

- 兩節都放在**截圖之前**、一句話開頭之後：要給推薦人看的 README 第一屏就該回答「為什麼做、做了什麼」，截圖接在後面
  正好示範條列裡的頁面。What it does 沒有移到安裝之後，改成把原本開頭那段（找發佈 → qBittorrent → TMDB → 硬鏈接 →
  帳本）併進條列，開頭只留一句，所以安裝必讀多出來的字有一部分是搬過來的。
- Why Berth 用第一人稱：那是作者本人的動機，寫成「我」最平實，也不必替 Seerr 那一套下判斷，只說「我覺得」。

### 字數

範圍照票 57：`README.md` 從開頭到〈The setup wizard〉的「Page by page…」那一行。算法是去掉程式碼區塊（含縮排的）、
連結網址與截圖之後用空白切字（讀者實際要讀的字）。

| | 本票前 | 本票後 |
| --- | --- | --- |
| 去掉程式碼、網址、截圖 | 556 | **703** |
| 原始 Markdown 直接切字 | 603 | 750 |

採第一列，703 在「約 700」內。為了壓進來，條列寫得比較短（例如精靈那一條沒寫「六頁」）；細節都在下面的段落與 guide。

### What it does 每一條的出處

| 條目 | 出處 |
| --- | --- |
| 作品頁搜 Prowlarr、自己挑 | `docs/guide/setup-wizard.md`〈After the wizard〉Title page 列 |
| Mikan、Nyaa、acg.rip 的 RSS 自動送出入庫 | 同表 RSS 列；CHANGELOG M3 票 08、11、19 |
| TMDB 認檔、硬鏈接、不佔兩份 | `docs/guide/requirements.md`；README 原本的開頭段 |
| 帳本與每晚檢查，列出處理方式 | 同表 Review / Issues 列；`berth/pipeline/reconciling.py`（04:00）、`berth/domain/enums.py` 的動作 |
| 健康頁每 5 分鐘 | `setup-wizard.md`〈After the wizard〉第一段；`berth/services/health.py` 的 `CHECK_INTERVAL` |
| 精靈：設好套件內或接既有、真檔案證明硬鏈接 | `setup-wizard.md` 頁 1–3 |
| 介面 zh-Hant / en | CHANGELOG 0.1.0「UI 語言 `zh-Hant` 與 `en` 並列」 |

候選裡的「設定精靈、套件內或接既有服務」寫成「設好」而不是「替你起」：套件內的服務是 compose 起的，精靈只設定與連接
（code-review Spec 指出）。每晚檢查寫「列出能怎麼處理」而不是「每一件都給修法」：硬鏈接被複製檔取代、大小又不同時
只列出來等人決定（同上）。

### upgrading.md 與斷鏈

刪了〈From 0.2.0 (the zip)〉整段。repo 裡沒有連到它錨點的連結；CHANGELOG `[0.2.1]` 那句「〈From 0.2.0 (the zip)〉」
連的是整個檔案、不是錨點，照票上「CHANGELOG 是歷史紀錄」留著，`[Unreleased]` 另記一行說那段拿掉了。

斷鏈掃描用 `tests/unit/test_readme_docs.py` 的 `broken_links`，對 `git ls-files '*.md'` 加本票共 264 個檔：
`264 files; 0 broken`。

### 驗證

- `uv run pytest tests/unit/test_readme_docs.py -q`：`34 passed`。
- `uv run pre-commit run --all-files`：全部 Passed。
- 沒跑 pytest / vitest / e2e 全套（只動文件，協調者指示），沒起任何容器。

### code-review 沒處理的發現

- Standards：What it does 的「用真的檔案證明硬鏈接」與精靈頁 3 的說明重複；Why 段與條列前兩條都講自己挑發佈與
  RSS。留著：條列是給只讀開頭的人看的摘要，重複是刻意的。
- Standards：條列第一條「a title's page」的 title 是 CONTEXT.md 列為避用的詞；README 截圖 alt 與 guide 本來就這樣寫，
  不在這張改。
- Standards：中文〈為什麼做 Berth〉留著英文 request：那是 Seerr 介面上的動作名，翻成「請求」反而對不上。
- Spec：多記了一行 CHANGELOG `[Unreleased]`（票上沒要求）：README 的改動以往都有記，照慣例。

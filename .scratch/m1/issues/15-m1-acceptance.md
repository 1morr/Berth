# 15 — M1 e2e 與里程碑收尾

**Status:** done

**Blocked by:** 13、14、14b、14c、14d、14e、14f

**讀:** plan §10、§11.2（T1.8）；brief §17（M1 那一列）

## 做什麼

把 M1 的整條路徑釘進 CI，然後收尾。

e2e 在 compose 環境跑：用本地產生的 `.torrent` 與檔案，以 `seedMode` 讓 torrent 立即完成，走通
送單 → 完成 → planning → importing → ledger → Jellyfin 反查，並驗證硬鏈接 inode 與 Jellyfin 真的
查得到 item。nightly 與 release 跑。

收尾包含 M1 六個新頁面的 `/impeccable critique`、`audit`、`polish`，以及票 01–14 的 Comments 逐條
過完——該延後的寫進 plan §11.3 而不是另開票（M0 票 11 的先例）。

## 驗收

- [x] compose 環境的 e2e 走通完整流程，用真的 qBittorrent 與真的 Jellyfin
- [x] e2e 驗證硬鏈接 inode 相同，且 Jellyfin 反查得到 item id
- [x] e2e 在 GitHub Actions 的 nightly 綠燈（附一次真的執行紀錄）——`e2e.yml` 手動觸發兩次都綠，排程觸發還沒輪到（見 Comments）
- [x] brief §17 的三部作品（美劇一季、動漫一季、電影）在真環境實跑一次並附證據
- [x] `/impeccable critique`、`audit`、`polish` 對 M1 的新頁面跑完，發現逐條處理或明確記錄為延後
- [x] `DESIGN.md` 依 M1 實際做出來的東西更新
- [x] README、CHANGELOG、CONTEXT.md 更新：`berth bench`、型別產生指令、新頁面與新名詞
- [x] 票 01–14 的 Comments 逐條過完；延後的寫進 plan §11.3，並在 `docs/progress.md` 記錄
- [x] lint / type / test / benchmark 門檻 / 前端測試全綠並貼指令輸出

## 驗證（2026-09-17，`b180aeb`）

```
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
275 files already formatted
$ uv run mypy
Success: no issues found in 204 source files
$ uv run lint-imports
Contracts: 6 kept, 0 broken.
$ uv run pytest
1341 passed, 4 deselected in 137.18s (0:02:17)
$ uv run berth bench
32 fixtures, 385 files
overall   385    385/385   188/188  171/171     172           0           79      0       42                 41             37                14
high: 0/84 wrong (0.0%)  medium: 0/88 wrong (0.0%)
$ pnpm -C web lint && pnpm -C web format:check && pnpm -C web typecheck
All matched files use Prettier code style!
$ pnpm -C web test
 Test Files  23 passed (23)
      Tests  323 passed (323)
$ pnpm -C web build
✓ built in 167ms
$ pnpm -C web gen:api && git diff --exit-code -- web/src/api/schema.d.ts
（無 diff）
$ uv run pre-commit run --all-files
（全部 Passed）
```

`4 deselected` 是 e2e（`-m 'not e2e'`）。`berth bench` 與 baseline 相同（172 / 0）。

**e2e**：

| 在哪裡 | 版本 | 結果 |
| --- | --- | --- |
| 本機 Docker Desktop（乾淨重建） | 工作目錄 | 4 passed in 797s |
| GitHub Actions [run 35187094041](https://github.com/1morr/Berth/actions/runs/35187094041)（workflow_dispatch） | `e76c21d` | 4 passed in 772s，job 14m08s |
| GitHub Actions [run 35194127527](https://github.com/1morr/Berth/actions/runs/35194127527)（workflow_dispatch） | `b180aeb`（最終版本，含 code-review 強化的斷言） | 4 passed in 773s，job 14m12s |

CI（`ci.yml`）在 `b180aeb` 上五個 job 全綠（run 35194117919）。

## Comments

### e2e 的做法（與票面字面不同的兩處）

- **recheck 取代 `seedMode`**：`seedMode` 是 qBittorrent Web API 2.16 起才有（5.2.3 是 2.15.1），而且要由送單的
  一方帶——那是 Berth。改成送單之後問 qBittorrent 下載路徑、把位元組放過去、`recheck`（票 12 驗收實證過的
  做法）。plan §10 已改。
- **打真的 TMDB**（使用者拍板）：精靈第 6 步是閘門，planning 也要真的快照。憑證是 repo secret `TMDB_API_KEY`，
  由本機 `.env` 以 `gh secret set` 設定，沒有印出值。季集對語料、不對集名（集名來自活的 TMDB，會被編輯）。
- Prowlarr 起來讓精靈偵測，第 5 步跳過索引站；送單直接帶 `torrents` 容器送的 `.torrent` 網址。搜尋不在 e2e 裡。
- 斷言：三筆都是 `imported` 且時間線依序走過 created → submitted → metadata_received → completed →
  plan_generated → linked → jellyfin_scan_requested、送單之後沒有任何人為事件；帳本的季集對語料；硬鏈接兩端
  在容器裡 `stat` 同一個 device / inode 且 nlink ≥ 2；帳本逐檔的 `jellyfin_item_id` 等於 Jellyfin 在那條路徑上的
  item、Episode 的季集是 Jellyfin 認的、媒體庫卡片的 Series / Movie 是 Jellyfin 以 TMDB id 認出來的那一個。
- **nightly 的排程**：`e2e.yml` 的 `schedule`（每天 18:23 UTC）在這個 session 結束前還沒輪到過；兩次真的執行都是
  同一份 workflow 的 `workflow_dispatch`。第一次排程跑完之後值得回頭看一眼 Actions。

### e2e 抓到的缺陷

- **每個請求的 commit 發生在回應送出之後**（`berth/api/deps.py`）：FastAPI 對 `yield` 相依的預設 scope 是
  `request`。第一輪 e2e 在精靈第 2 步回 200 之後馬上打第 3 步，讀到的 Jellyfin 位址還是空的
  （`UnsupportedProtocol`）。改成 `scope="function"`，紅燈測試在回應開始的那一刻另開連線讀資料庫。

### brief §17 的三部作品（真環境證據）

本機那一輪（Berth 由工作目錄 build、qBittorrent 5.2.3、Jellyfin 12.1.0、Prowlarr、真的 TMDB；`/data` 是 Docker
Desktop VM 的 ext4 named volume）。Jellyfin 以管理員 token 查 `/Items`：

```
Movie:  奧本海默 (2023)   Tmdb=872585 poster=200 image/jpeg 201689B
        /data/library/movies/Oppenheimer (2023) [tmdbid-872585]/Oppenheimer (2023) [tmdbid-872585] - [BD][1080p][YTS.MX].mp4
Series: 大熊餐廳 (2022)   Tmdb=136315 poster=200 image/jpeg 1483359B   S3: 10 集（1 翌日 … 10 永遠）
Series: 葬送的芙莉蓮 (2023) Tmdb=209867 poster=200 image/jpeg 956010B  S0: 11 集、S1: 28 集（1 冒險結束 … 28 因為下次再見時會很難為情）
```

Berth 的媒體庫：大熊餐廳 10 / 46 集入庫、葬送的芙莉蓮 28 / 38 集入庫、奧本海默完整，三格都「在 Jellyfin 開啟」，
item id 與上面相同。帳本 50 筆正片的 `jellyfin_item_id` 50 / 50 等於 Jellyfin 在那條路徑上的 item。容器內 `stat`：

```
196201 2 /data/torrent/complete/tv/The.Bear.S03.COMPLETE.1080p.HULU.WEB.H264-SuccessfulCrab[TGx]/The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv
196201 2 /data/library/tv/The Bear (2022) [tmdbid-136315]/Season 03/The Bear (2022) - S03E01 - Tomorrow [WEB][1080p][SuccessfulCrab].mkv
```

票 12 / 14b 留下的舊驗收環境為此 `docker compose -p berth down`（沒有 `-v`：`berth_berth-m1-data` volume 與舊
session scratchpad 裡的設定目錄都還在），因為容器名、網路與 port 撞在一起。

### `/impeccable critique` → `audit` → `polish`（M1 的新頁面）

「六個新頁面」取為探索、Media 詳情、搜尋結果（詳情頁裡的一區，在 fake `submit` 情境看）、下載、媒體庫、Route
設定。

- **critique**：26 / 40，dual-agent，報告 `.impeccable/critique/2026-09-17T06-17-18Z__web-src-pages.md`。
  檢測器 CLI 0 findings；頁內 overlay 的 `text-occlusion` 是誤報（收合 `<details>` 的內容沒有渲染）。
  使用者拍板：修 P1 三條（390px 破版、medium 待確認看不見、送單的焦點與錯誤）加結構性無障礙；詳情頁版面交
  M1.5 的 shape（這一票只做連續 `linked` 合成一行與「展開 / 收起」）；顯示用標題的語言記進 brief §19。
- **audit**（改動之前）：a11y 2、效能 3、響應式 2、主題 4、實作一致性 3，14 / 20。細目在 `docs/progress.md`。
- **polish**（改完之後）：playwright 在 e2e 那一套量五頁 × 深淺 × 1280 / 390，頁面層級橫向捲動全 0，最低對比
  深色 6.53:1、亮色 5.71:1；console 零錯誤；鍵盤走過 skip link（浮出時 90×35px）與送單確認（展開時焦點在確認、
  Esc 回送單鍵、送出後 `role="status"` 宣告、焦點落在「看下載列表」）；檢測器對改過的檔案 0 findings。
- 沒做、已記錄：詳情頁版面與展開沒有上限（plan §11.2b）；critique 的其餘小項（plan §11.3 的兩條）。
- critique 的 snapshot 沒有 close：第 5 條（詳情頁版面）交給了 M1.5，Priority Issues 沒有全部清掉。

### 票 01–14f 的 Comments

逐條的判定在 `docs/progress.md` 的偏差與決定（三條：修掉的、延後的、不排里程碑的）。修掉的四條：凍結資料夾名
沒被 planning 讀、`inventory._survey` 前綴沒正規化、PowerShell 下 `deploy/` 腳本測試全紅、英文單複數。延後的在
plan §11.3（M2）、§11.4（M3）、§11.2b（M1.5）；兩條產品問題在 brief §19 待決（TMDB 連不上就走不完精靈、顯示用
標題的語言）。票 14 / 14e 點名留給這一票的精靈泊位 4 剖面兩條由 code-review 帶出、已修。

### code-review（兩軸，基準 `d5027a6`）

處理了的在 `docs/progress.md`。**沒處理**：

- `747f20f` 與 `31cfd72` 的 commit body 各有一行 73–74 字元（全域 CLAUDE.md〈Git〉）。兩個都已經 push，改寫要
  force push。
- audit 計數在 `services/jobs._view`（逐筆）與 `services/inventory._audits`（批次）形狀相近，聚合粒度不同，不合併。

### 其他

- 實跑時 **cookie 不分 port**：在 8484（fake 情境）登入會蓋掉 8383 的 session。
- fake `inventory` 情境把 demo torrent 網址寫死成 8484，換 port 就送不了單（plan §11.3 記了）。

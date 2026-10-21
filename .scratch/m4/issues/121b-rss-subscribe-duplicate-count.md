# 121b — 前端 e2e `rss-subscribe`：acg.rip 第一輪預覽時而多出「重複 2」

**Status:** done

**Blocked by:** None — can start immediately（排在 124 之前；跟 123 並行，123 不碰 RSS）

**讀:** 票 13b（同一條 spec 上一次的修法與 Comments）；`web/e2e/rss-subscribe.spec.ts`；plan §6 rss（預覽、重複的判定）；
progress.md 2026-09-27 票 13b 那一行

## 為什麼

`web/e2e/rss-subscribe.spec.ts:42`（1280 那份）第二次紅在同一個斷言，兩次都在跟 RSS 無關的 commit 上：

- 2026-10-13 CI run 38405255701（`d07daa3`，只改文件）
- 2026-10-21 CI run 39556789559（`718e2a7`，合併票 121：只有文件、fixture 與實驗腳本）

預期 `會送出 30 · 綁定之後送 0`，實際 `會送出 28 · 綁定之後送 0 · 排除 0 · 重複 2`。同一輪的 `rss-subscribe-390` 是綠的。
這跟 13b 的逾時不是同一種失敗：預覽有回來，只是兩筆被算成重複。前面一步剛從作品頁訂閱了 Mikan 的
LoliHouse（送出 12 集），acg.rip 搜尋 feed 裡也有 `[喵萌奶茶屋&LoliHouse]` 的條目，懷疑重複的判定取決於
前一步的送出有沒有在預覽之前落地。這只是線索，還沒有 repro。

## 做什麼

先分清楚是**產品的問題**（同樣的操作，使用者看到的「重複」數會隨時序變，代表判定本身不穩）還是 **spec 的問題**
（spec 假設的時序或測試資料不對；例如那兩筆照規則本來就該算重複，30 才是錯的期待）。前者修產品，後者修 spec
並說明為什麼原本的期待不對。不接受只拉長逾時、加 retry 或放寬斷言而說不出原因。

## 驗收條件

- [x] 原因寫進票的 Comments：哪兩筆被算成重複、跟誰重複、為什麼有時算有時不算，附證據（log、trace 或計時）
- [x] 有一條會紅的 repro：產品的問題就是後端整合測試（修好轉綠）；spec 的問題就是能穩定重現兩種結果的步驟
- [x] `rss-subscribe` 與 `rss-subscribe-390` 在整套前端 e2e 裡連跑三次都綠
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 有 session 紀錄

## Comments

- **原因：spec 的問題，判定本身是穩的**。重複的兩筆是 acg.rip 搜尋 feed 裡的
  `[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 11` 與 `- 12`
  （`[WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]`），與 Mikan 單一 feed 的 11、12 集發佈名一字不差。
  理由是 `in_library`，對上的是前一步 Mikan 補舊集剛入庫的
  `Kimi ga Shinu made Koi wo Shitai (2026) - S01E11 / S01E12 [WEB][1080p][CHS+CHT+JP][LoliHouse].mkv`。
  acg.rip 不報 info hash（brief §20、plan §8.5：送單時才算），所以同一個 torrent 那一層比不到它們，
  擋下的是帳本那一層（`_held_back` → `_in_library` → `library_copy`）。
- **為什麼有時算、有時不算**：預覽照**當下的帳本**去重、只讀不寫（`preview_feed` 的 docstring，brief §15
  「處理」：GUID → info hash → 帳本已有同 Media / 季 / 集 / Tags）。在路上、還沒入庫的 Job 只有 info hash
  那一層看得到，acg.rip 的 Item 沒有 hash；帳本那一層（`library_copy`）只看已入庫的。
  `rss` 情境的替身 qBittorrent 收下就完成，Mikan 那 12 集在訂閱之後約 5–6 秒規劃完、入庫；spec 在訂閱
  之後只做幾個斷言與截圖就建 acg.rip feed、讀預覽，兩件事在賽跑。預覽先到是 30 筆會送出，入庫先到是
  28 + 重複 2——照規則後者才對：那兩集已經在媒體庫裡。spec 的 30 是「預覽搶在入庫之前」才成立的期待。
- **證據**（`scripts/experiments/rss_subscribe_timing.py --watch 15`，建好 feed 之後每 0.5 秒讀一次預覽
  與 `/jobs`，有變化才印；t 從送出訂閱起算），連跑三次都是同一個形狀：
  ```
  t=  1.2s preview={'matched': 30} mikan jobs imported 0/12
  t=  5.3s preview={'matched': 30} mikan jobs imported 5/12
  t=  5.9s preview={'duplicate': 2, 'matched': 28} mikan jobs imported 12/12
      duplicate: [喵萌奶茶屋&LoliHouse] … - 12 … <- in_library {'known': '… S01E12 [WEB][1080p][CHS+CHT+JP][LoliHouse].mkv'}
      duplicate: [喵萌奶茶屋&LoliHouse] … - 11 … <- in_library {'known': '… S01E11 [WEB][1080p][CHS+CHT+JP][LoliHouse].mkv'}
  ```
  另兩次在 t=1.1 / 1.2 s 是 30、t=6.4 / 5.9 s 變成 28 + 2。這就是 repro：同一串步驟，入庫前讀到 30、
  入庫後讀到 28 + 重複 2，看的是 11、12 兩集入庫了沒有。兩次 CI 紅燈的實際值（`會送出 28 · 綁定之後送 0 ·
  排除 0 · 重複 2`）就是入庫之後的那一種。
- **修法（spec）**：訂閱之後先到 `/jobs?filter=all` 等 12 筆都「已入庫」（同 `rss.spec.ts` 的等法），再回
  作品頁建 acg.rip feed，期待 `會送出 28 · 綁定之後送 0 · 排除 0 · 重複 2`，展開「看重複（2 筆）」看得到
  兩條「媒體庫裡已經有同一個版本」與 S01E11 / S01E12 的檔名。帳本只會長，等到入庫之後結果就定了；這樣
  也讓這條 spec 演到跨 Feed 的帳本去重。最後「只追之後的」之後下載列表仍是那 12 筆。產品沒改。
- **沒修、留著的**：入庫之前那幾秒，預覽把這兩筆列在「會送出」。真的選「全部下載」時送單那一刻會再看一次：
  帳本有了就是重複；還沒有的話 `add_download` 抓 `.torrent` 算 hash，與 Mikan 那一筆同一個 hash 就是
  `same_torrent`，不同（brief §20 記為未證實）才會多下載一次，再由規劃時的重複版本判斷（brief §7.8）接住。
  這是 brief §15「漏擋只是多下載一次」那條取捨；要讓預覽也看在路上的 Job 是新規則，沒有失效情境之前不動。
- 結果：整套前端 e2e 連跑三次都是 38 passed，`rss-subscribe` 6.9 / 8.0 / 9.0 s、`rss-subscribe-390`
  7.7 / 9.6 / 5.3 s。那段時間另一個工作樹（票 123）佔著 config 的 port，所以這三輪用一份不 commit 的暫時
  config 把每台演練 server 的 port 平移 +1000 跑（`sed -E 's/port: 8([45][0-9][0-9])/port: 9\1/'`），其餘與
  `playwright.config.ts` 相同，跑完刪掉。pre-commit 全過（ruff、ruff format、mypy、import-linter、prettier、
  eslint、knip）、tsc 綠、vitest 2081 passed、pytest 4106 passed / 2 skipped。第一次以 `-x` 跑 pytest 時
  `test_health_api.py::…test_it_turns_degraded_when_a_check_fails` 一條 ERROR（setup 階段），單獨跑 19 passed、
  整套重跑不重現；這一票沒碰後端，沒追。產品沒改，不必跑 `berth bench`。
- code-review 處理掉的：實驗腳本的 `# type: ignore` 改成 `isinstance(sys.stdout, io.TextIOWrapper)`（同
  `rss_sources.py`）、`--watch` 的比較改用具名變數（Standards）；上面「在路上的 Job」那一句原本說成不在規則裡，
  改成「只有 info hash 那一層看得到」，並補 CI 實際值就是入庫之後那一種（Spec）。
- code-review 留著的：spec 等 12 筆入庫的四行與 `rss.spec.ts` 那一段一字不差（Duplicated Code，判斷題）；
  e2e 各條 spec 本來就各寫各的等待，抽 helper 只為兩處不值得。

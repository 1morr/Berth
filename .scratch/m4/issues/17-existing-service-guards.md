# 17 — 既有服務防呆：`localhost` 提示、版本門檻說明、Prowlarr 版本下限

**Status:** done

**Blocked by:** None — can start immediately（不依賴 15；提示要掛在 15 的「既有」表單上，建議排在 15 之後，先做的話掛在現在的連線表單、15 搬過去）

**讀:** brief §16.4（既有服務要給的東西、容器裡的 `localhost`、健康檢查會擋下的情況）、§20.9、§20.14；plan §9.3〈服務頁的共同形狀〉、§9.5；`.scratch/m4/wizard-manual-choice-decision.md`〈規則〉

## 為什麼

選「既有」之後最常見的兩種卡住（2026-09-29 協調者整理，brief §20.14）：

- **填 `localhost` / `127.0.0.1`**：Berth 在容器裡，那指的是 Berth 自己，測試只會說「連不上」，看不出原因。
- **版本太舊**：Jellyfin 低於 12.0、qBittorrent 低於 4.4 現在是紅燈，但選「既有」之前沒有人告訴使用者有門檻；
  Prowlarr 的下限**根本沒定**——Berth 用到的 `indexer/schema`、`indexer/test`、`search`、`config/host` 在舊版上
  可能不存在，失敗時說不出原因。

## 做什麼

1. **查證 Prowlarr 版本下限**（`mattpocock-skills:research`，輸出 `docs/research/`）：Berth 用到的每一支端點
   （`berth/adapters/` 裡 Prowlarr 那一支 adapter 全列）從哪一版起有；取最高者當下限。結論與來源寫進 brief §20.14
   （取代那一條「待查證」）、§16.4 與 plan §9.5〈既有 Prowlarr〉。
2. **Prowlarr 的版本檢查**：照 Jellyfin `public_info().supported` 的形狀（plan §8.2），精靈測試與健康檢查用同一個判斷、
   同一句原文；低於下限停在 Prowlarr 頁、說出目前版本與下限。Torznab 端點（Jackett）不在此列。
3. **`localhost` 提示**：既有服務的位址主機是 `localhost`、`127.0.0.1`、`::1`（含 `[::1]`）時，欄位下就地提示：
   Berth 在容器裡，改填 `host.docker.internal`（Docker Desktop 內建；Linux 靠 16 的 `extra_hosts`，且服務要監聽
   `0.0.0.0`）或區網 IP。只提示、不擋（`network_mode: host` 之類的部署填 `localhost` 是對的）。判斷是一支純函式，
   前端用它；測試不過時的錯誤訊息也帶同一句。
4. **版本門檻說明**：三個服務頁的「既有」選項旁說出下限（Jellyfin 12.0 附升級注意的連結、qBittorrent 4.4、
   Prowlarr 照第 1 點）；zh-Hant 與 en 並列。

## 驗收

- [x] Prowlarr 版本下限與來源寫進 brief §20.14、§16.4、plan §9.5；研究檔在 `docs/research/`
- [x] Prowlarr 低於下限時精靈與健康檢查都說出目前版本與下限（整合測試：Fake 回舊版本；雙向：剛好等於下限時通過）
- [x] `localhost` / `127.0.0.1` / `[::1]` 出提示，`host.docker.internal`、區網 IP、compose 主機名不出（單元測試或 vitest，雙向）
- [x] 三個「既有」選項旁有版本下限（vitest 或 playwright 文字結果，zh-Hant 與 en）
- [x] `berth-lab` existing 用 playwright 實跑：填 `localhost:38096` 看到提示、改 `host.docker.internal:38096` 之後接得上
- [x] lint、type、test 綠燈

## Comments

**2026-09-29 實作紀錄**

- berth-lab existing 實跑（`berth:m4-17`，playwright，owner 已成立的那一份設定；位址已改回 `host.docker.internal`）：
  Jellyfin 頁「改位址或憑證」→ 填 `http://localhost:38096`，位址欄下出現「Berth 在容器裡，這個位址指的是 Berth 自己…」；
  按測試連線 → 紅燈「主機名解得到但連不上」、手動步驟是同一句；改 `http://host.docker.internal:38096` → 欄位下的提示收起、
  測試綠燈「連上了，已經有管理員 · 版本 12.1.0」。「既有」卡上是「版本下限：Jellyfin 12.0。從 10.x 升級是單向的，先看
  升級注意。」加連結 `https://jellyfin.org/posts/jellyfin-release-12.0/#tl-dr`。berth-lab `existing/docker-compose.yml`
  的 image 改成 `berth:m4-17`（repo 外）。
- `127.0.0.0/8` 整段都當迴路（票只列 `127.0.0.1`）；`.localhost` 子網域與 `0.0.0.0` 不提示。
- 套件內 Prowlarr 太舊也當場紅（`_test_connection` 共用同一個判斷），補法是 `docker compose pull prowlarr`。

**code-review 未處理的發現**

- 同一個下限寫在三處：`adapters/prowlarr.MIN_VERSION`、i18n 的 `choice.existing.floor.*`（zh-Hant / en）、vitest 的字串。
  沒有閘門把前端文案綁到後端常數；Jellyfin 與 qBittorrent 的下限本來就是同樣的形狀，要綁就三個一起（例如 `/setup/status`
  帶下限、文案用插值），不在這一票。
- `indexer.probe_indexer` 與 `setup._test_connection` 的 Prowlarr 分支各寫一遍「ping → 版本 → 列站」（ping → 列站的重複
  原本就有）：前者把錯誤收成 `SetupStep`、後者要例外分類，合不起來除非 `_classified` 搬家。
- `_Outcome.detail` 一欄兩用（站數或版本），`_existing_indexer_step` 靠理由分辨；`unsupported_message` Jellyfin 與 Prowlarr
  各一支。
- `probe_indexer` 失敗的理由只分得出「版本太舊」與其餘（一律 `unreachable`，含帳密錯）：既有行為，沒有 repro 不動。

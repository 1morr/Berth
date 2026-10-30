# 05c — plan 去歷史：§6–§7（API 面、前端）

**Status:** done

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §6–§7（只有 63 行卻有 83 KB，§6 平均一行 1.6 KB）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。§6 是最難讀的一節：44 行 70 KB。

## 做什麼

照 spec〈改寫規則〉改寫 plan §6–§7。章節與小節號不變（§6 被 `berth/` 引用 119 次）。§6 的表格一列一個端點群，長說明拆到表下的清單；端點與欄位對照 `web/src/api/schema.d.ts` 確認現況。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§6–§7 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

### 前後（`7a7f7419` → 本 commit，§6–§7）

| | 行 | 大小 | 歷史標記（票規定的 regex，逐次出現） |
| --- | --- | --- | --- |
| 前 | 61 | 85,897 B | 253（36 行） |
| 後 | 約 360 | 約 87 KB | 2 |

大小沒有縮：長段落拆成清單與小標，另補了舊版漏的內容（見下）；目標是讀得懂，不是位元組。剩下的 2 處是連結檔名裡的日期（`m5-ai-direction-2026-10-27.md`、`m5-acceptance-2026-10-28.md`），是唯一證據指標，不是歷史敘述。保留的 `.scratch/m*/…-shape.md` 連結是設計理由的唯一來源（Spec 軸建議保留）。

### 對照表（舊 → 新，章節號不變）

| 舊版 | 新版 |
| --- | --- |
| §6 開頭三段（門禁預設拒絕、白名單、`setup/*` 規則、admin 前綴與 `ADMIN_ROUTES`、Route 刪除走 `setup/routes`、`health`、cookie/CSRF） | §6〈門禁與 session〉 |
| 表 auth / setup / settings | 總表一列一群；§6 `#### auth` / `setup`（狀態、服務選擇、Jellyfin、qBittorrent、索引站、TMDB 與 Route 分組）/ `settings` / `/me/notifications` |
| routes / discover / inventory / jellyfin | `#### routes` / `discover` / `inventory` / `jellyfin`（權限在 `jellyfin_access`、圖片白名單、CSP、快取例外） |
| media（含 why-not、集照播出日對 TMDB） | `#### media` |
| search / jobs / plans / review / files | `#### search`（分批、`from_season`）/ `jobs` / `plans`（`apply_to_series`）/ `review`（四類）/ `files` |
| rss | `#### rss`，分 Feed / Series / Item / 排除條件 / 一次性連結與訂閱 |
| issues / weekly / agent / proposals / health / events | 同名 `####` |
| 底下 bullet：Cache-Control、OpenAPI 契約、命令執行器、agent runtime、防護、skills、MCP | §6〈跨端點的規則〉 |
| §7 路由、守衛、資料、送出中、文案、主題、版面、無障礙 | §7〈路由〉表、〈守衛〉、〈資料與互動〉 |
| §7 元件（review、Job 詳情） | §7〈元件〉 |
| §7 側面板 | §7〈側面板〉 |
| §7 確認卡（Route、字幕組、`held`、恢復、數量閘）、守法 | §7〈確認卡〉、〈守法〉 |

被刪的只有日期、票號、「推翻」「原寫」「使用者拍板」與已不存在的端點敘述（`GET /jellyfin/watching`、`/health/budget`、`DELETE /setup/services/qbittorrent/leftovers/categories`、`/setup/indexers/connect`、tmdbid 搜尋、請求預算欄位）。

### 對照程式後的修正（舊版缺或錯）

- 補：`/settings/ai` 四支與拒絕碼、`PUT /setup/jellyfin/bundled`、`POST /setup/routes/libraries`、`/weekly*`、`/agent/runs/:runId`、`/settings/ai|usage|notifications` 路由與依角色的 `/settings` 導向、通知頁一般使用者可進。
- 修：`setup/*` 門禁照 `SETUP_OPENING_PATHS`（擁有者成立之後，精靈未完成也只有 admin）；agent 工具清單補 `downloading.add_manual_download`、`discover.read_trending`、`ANIME_TOOLS`、Tavily 條件。

### Spec 軸（opus 子代理逐段比對舊版）

缺漏 1 項（`test_openapi_contract.py` 守著的說明）、意思被改 2 處（`indexers/test` 的 422 主詞、`release` 的 `route_missing` 條件）、新增錯誤 4 處（工具清單、`setup/*` 矛盾句、`bundled` 缺拒絕、精靈頁碼不一致）、設計稿連結被刪——全部已補回或修正。§7 無缺漏。

### 要問使用者的矛盾

沒有 plan 與 brief 的矛盾要你挑。小事：舊版的精靈頁碼不一致（Route 刪除寫「第 5 步」與「頁 3」），我改成「Route 那一頁」；正確頁序以 §9.3 為準，你若要精確頁碼請告知。

### 驗證

`uv run pre-commit run --all-files` 全過；`pytest tests/unit -k "docs or readme or progress or reading or link or plan or openapi or executor or skills"` 552 passed。（只改文件，未跑整個 test。）

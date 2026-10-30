# 05e — plan 去歷史：§9（開箱即用）

**Status:** done

**Blocked by:** 02, 04a

**讀:** `.scratch/docs-diet/spec.md`（〈共同規則〉〈改寫規則〉）；plan §9（約 230 行 86 KB，plan 最大的一章）；`docs/adr/` 的索引（brief §19）；改寫時遇到引用 brief 的地方才讀那一節

## 為什麼

plan 每行平均 330 bytes，117 處日期、1,007 處「票 NN」、12 處「推翻」混在規格裡，讀的人要自己拼出現況。plan 太大，按章節拆成 05a–05e，可以並行，後做的先 rebase。

## 做什麼

照 spec〈改寫規則〉改寫 plan §9。章節與小節號不變（§9.3、§9.5 被 `berth/` 引用 40–90 次）。§9 的精靈流程對照 brief §16.3、§16.4（04c 改寫後的版本）。

## 驗收

- [x] 前後大小與歷史標記數貼 Comments；剩下的標記逐條有理由
- [x] 對照表貼 Comments，§9 每個決定、規則、欄位、端點、數值都對到新版位置或 ADR
- [x] 收尾 code-review 的 Spec 軸照對照表逐節比對舊版，結果貼 Comments
- [x] 發現 plan 與 brief 的矛盾列在 Comments 問使用者，沒有自己挑
- [x] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments

### 前後大小與歷史標記（開工 commit `e4aaec5b`）

| | 舊 | 新 |
| --- | --- | --- |
| §9 大小 | 231 行、88,579 bytes | 555 行、83,707 bytes（長段拆成清單，行數增加） |
| 歷史標記（spec 的 regex，行數） | 102 行（228 處） | 0 |

剩下的標記：0，不需逐條說明。保留的證據指標改成連結：ADR-0002、0009、0010、0011、0012、0013；`.scratch/m4/` 的 shape 檔（service-pages、error-layers、route-berth、route-auto-run、existing-new-library、indexer-berth、wizard-navigation）；brief §20.x。

### 對照表（舊 → 新，章節號不變）

| 舊版 | 新版 |
| --- | --- |
| 9.1 四服務表、Image/網路/healthcheck/多階段 build/非 root | 9.1 表與〈Image 與網路〉 |
| 9.1 `.env.example` 五 port、profile、`.env` 只放主機端事實 | 9.1〈`.env` 與 profile〉，ADR-0009 |
| 9.1 `berth-` 容器名、`extra_hosts` | 9.1〈容器名與主機〉 |
| 9.1 Windows、單一 compose、只有 compose 加 `.env`、Release 附件、Compose 2.23.1 | 9.1〈平台與發佈〉 |
| 9.1 incomplete/complete 根、目錄骨架 | 9.1〈目錄〉 |
| 9.2 白名單兩鍵、缺鍵才補、ServerDomains、WebUI port 內外一致、不預置全域鍵、白名單被關的補法 | 9.2 同序條列 |
| 9.2 Prowlarr、Jellyfin 不預置 | 9.2 末兩段 |
| 9.3 開頭（逐服務選、`settings.setup.choices`、未選拒絕寫入） | 9.3 開頭條列 |
| 9.3 六頁表、頁序理由 | 9.3 表與其下條列 |
| 共同形狀：二選一、不預選、送出回饋、「既有」旁說明、`stop`、撞 port | 〈服務頁的共同形狀〉來源二選一 |
| 共同形狀：compose 主機名、localhost 提示、版本下限 | 〈位址與連線〉 |
| 進頁只查主機名、`GET /setup/compose` | 〈進頁只查主機名〉 |
| 選完就測、既有測過才存、`connection_failed`、套件內三種失敗、`scheme_*`、版本擋 | 〈選完就測；既有的測過才存〉 |
| 表單跟著狀態走、已設過登入怎麼認、點選才算數 | 〈表單與狀態〉 |
| 回頭改選擇（Jellyfin 鎖、`other_server`、`unverified`、ConfirmPanel、LeftoverList、`forget_route_checks`） | 〈回頭改選擇〉 |
| 錯誤分三層（代碼、requestProblem、401/403、技術細節、eslint、forgetResults、`auth_failures`、欄位標示） | 〈錯誤分三層〉 |
| 頁 1 全部（existing 單表單、claim_owner、OwnerRefusal、帳密只送測過的、門禁、`data_unseen`） | 〈各頁〉1 |
| 頁 2 套件內（沿用、帶過來、必填、規則、雜湊、設定頁）、看得到 `/data`、既有、全域偏好不寫 | 〈各頁〉2 |
| 頁 3 清單、既有勾選、Route、自動建立、輪詢、重跑 | 〈各頁〉3 |
| 頁 4 套件內 key/登入/站、主鍵、`unlisted`、進階加站、已加入與試搜、進頁只讀、既有、跳過 | 〈各頁〉4 |
| 頁 5 TMDB、頁 6 完成 | 〈各頁〉5、6 |
| 續行與跳過 | 〈續行與跳過〉表與條列 |
| 前端的導覽 | 〈前端的導覽〉 |
| 9.4 步驟 1–7、分兩半、第 8、9 步移除 | 9.4 同序；〈不做的事〉 |
| 9.5 掛載規則、NAS 範例、stop、連線位址 | 9.5 同序 |
| 9.5 既有 Jellyfin/qBittorrent/Prowlarr | 9.5 三個小節 |
| 9.5 六條檢查、補法、套件內 Route 範圍、不支援 | 9.5〈檢查與訊息〉〈套件內的 Route 範圍〉 |
| 9.6 | 9.6 不變 |

被刪掉的純歷史：舊 9.3 開頭兩段「改」註記、migration `e8a1c4d7b293`、danieladov 插件庫與合併任務 `Id`、「票 NN 之前」的舊行為、Unraid「檔案在隨身碟上」括號。

### Spec 軸比對（opus 子代理，逐節對舊版 `git show e4aaec5b:docs/plan.md`）

找到 4 處意思變了、1 處憑空主張、2 處語氣，已全部修正：換台確認的纜繩說明、「5.2 帳號先寫」、`probe_indexer` 不再列頁 4、〈續行與跳過〉表「完成」改「以上都不成立」、「5.2 起的 API key 目前不做」、拿掉「唯一例外是勾選站」。其餘數值、端點、代碼、測試檔名逐一對過，沒有漏。

### 矛盾，請使用者決定（我沒有挑）

1. plan §9.2 寫「Berth 從同名環境變數組出偵測的位址…判成套件內之後…判定記下的那一條」，brief §16.3 與 plan §9.3 都說不偵測、不判定。
2. plan §9.3〈「既有」旁說明〉寫選既有時那一頁就給 `COMPOSE_PROFILES` 與 `docker compose stop`；brief §16.3、plan §9.1、§9.5 寫只在完成頁給一次。
3. plan §9.3 寫換台時連不到可「一鍵移除空的 `berth-*` 分類」；brief §16.4〈換一台時〉寫移除是換台框的勾選（預設不勾），原台沒答上來整個換台不做（`categories_not_removed`）。
4. brief §16.3 寫精靈 qBittorrent 頁「會列出已預置的項目」；plan 頁 2 纜繩只剩 `web_ui_password`，`web/src`、`berth/` 也搜不到「已預置」。
5. brief §16.4 寫換走套件內 qBittorrent 時換台框多列免密白名單與關法；plan 換台清單沒有這項（少列，非直接矛盾）。
6. ADR-0011 稱 TMDB 是「精靈第 6 步的閘門」，plan 現在是頁 5（ADR 的舊編號）。

### 驗證

`uv run pre-commit run --all-files` 全過；`uv run pytest tests/unit` 2180 passed。

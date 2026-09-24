# 06h — 精靈驗收：冷啟動閘門、兩條完整路徑、impeccable 收尾

**Status:** ready-for-agent

**Blocked by:** 06b、06c、06d、06e、06f、06g（全部做完才驗）

**讀:** plan §9.1–§9.5、§10（e2e）；`.scratch/m0/wizard-shape.md`；06b–06g 六張票的驗收與 Comments；`tests/e2e/conftest.py`（`configured`）、`.github/workflows/e2e.yml`、`web/e2e/wizard.spec.ts`、`scripts/fake_setup_server.py`（`starting` 等情境）；README〈快速開始〉的泊位表與〈前端 e2e〉

## 做什麼

06b–06g 由六個 session 各改精靈的一塊：port 進 `.env`、第 1 步剖面與帳密、導覽（停在結果上、上一個 / 下一個泊位、泊位板可點、Route 自動跑）、泊位板 4 格變 5 格與索引站試搜、自訂媒體庫、偵測時服務還在啟動。每張票只驗自己那一塊，**這一張驗整條路還走得通**，並把使用者 2026-09-24/25 試跑時靠手動才發現的事變成常駐的閘門（全域規則：手動驗證過但沒編碼進去的等於沒驗證）。

**為什麼現有的測試沒擋下 06g**（使用者 2026-09-25 問「要不要寫一個精靈的驗收票」時查到）：

- `tests/e2e` 用 `docker compose up --detach --build --wait`（`.github/workflows/e2e.yml`），**四個容器都健康了才開始精靈**，永遠碰不到 Jellyfin 還在啟動的那幾秒；`conftest.configured` 的 `detected` 在逾時時自己按 `restart`，又補掉一層。
- `web/e2e/wizard.spec.ts` 只有一條，對替身 `bundled` 走套件內的路；替身的 `starting` 只演 qBittorrent 連不上與 Prowlarr 讀不到 key，沒有 Jellyfin 的 503 與半啟動；既有服務（`mixed`）沒有端到端的一條。

要做的：

1. **冷啟動 e2e**：真的 compose 起來之後，**不等外部服務健康就開始精靈**（`--wait` 只等 `berth`，或 workflow 拆成先起 berth），`configured` 拿掉逾時就 `restart` 的補救，照常輪詢到判定完成。四個容器同時啟動、全程不按重新探測就走完。這是 06g 的常駐閘門。
2. **替身補情境**：`starting` 加上 Jellyfin 回 503 「still loading」與回應不像 Jellyfin 的半啟動（06g 量到的兩種），本機 playwright 就重現得出來。
3. **playwright 兩條完整路徑**（1280 與 390，zh-Hant）：
   - 套件內：5 格泊位、每一格做完停在結果上、按「上一個泊位」回去再往前、從泊位板點回走過的泊位、自訂一個媒體庫（改名、加一列、刪一列）、試搜索引站並移除一站、Route 自動跑、完成後以同一組帳密登入。
   - 既有服務（`mixed`）：Jellyfin 勾選媒體庫與選寫入目標、既有 qBittorrent 的帳密、既有 Prowlarr。
   - 另外一條冷啟動（替身 `starting`）：不按重新探測就判定完成。
4. **`/impeccable critique`、`audit`、`polish` 各一輪只對精靈**：P0 / P1 當場修，其餘記進這張票的 Comments（專案 CLAUDE.md：UI 收尾前）。
5. **文件一致**：README 的泊位表（現在是四個泊位）、plan §9.3 的步驟與前端覆寫規則、`.scratch/m0/wizard-shape.md`、CONTEXT.md 的名詞、`.env.example`，都對得上做出來的畫面。
6. **使用者實走一次**：試跑環境（`C:\Users\Roxy\berth-trial\`，非預設 port）改用 06b 之後的 compose 與 `.env`，重置後從第 1 步走完；**不靠 `WebUI\HostHeaderValidation=false`**——試跑目錄的 preseed 副本裡那一行要一起拿掉（06b 的 Comments）。走完之後媒體庫的「在 Jellyfin 開啟」開到對外 port。

## 驗收

- [ ] 冷啟動 e2e 在 CI 綠燈：精靈在外部服務還沒健康時就開始，`configured` 不再按 `restart`（貼 CI run 連結與輸出）；把 06g 的修正拿掉時這一條會紅（在 PR 描述或票的 Comments 記下實跑結果）
- [ ] 替身 `starting` 有 Jellyfin 的 503 與半啟動，README 的情境表同步
- [ ] playwright：套件內、既有、冷啟動三條，1280 與 390 截圖附在票上
- [ ] `/impeccable critique`、`audit`、`polish` 各一輪，分數與處理結果記在票上
- [ ] README、plan §9.3、`wizard-shape.md`、CONTEXT.md、`.env.example` 與畫面一致
- [ ] 使用者在試跑環境重置後走完一次，沒有用到 `HostHeaderValidation=false`，也沒有按重新探測；結果記在 Comments
- [ ] lint、type、test、e2e 全綠（貼指令輸出）

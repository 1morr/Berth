# 15 — 片長驗證

**Status:** done

**Blocked by:** None — can start immediately（mediainfo 與 TMDB 片長都已經有了）

**讀:** plan §3.1（`planning` → `review`）、§4.2、§8.7、§11.4（「入庫前後的三道程式檢查」②）；brief §6.2（「分類器要能被 mediainfo 修正」）、§6.10、§14

## 做什麼

三道程式檢查的第二道：mediainfo 量到的片長與 TMDB 那一集的片長差太多時，不自動入庫。

- **抓什麼**：分類錯誤，像預告、NCOP、SP / OVA、兩集合併檔被當成一集正片。**抓不到**同一季裡算錯的集號（那是票 14 的事）。
- **門檻**：比例與絕對秒數怎麼定，先用 benchmark 語料裡有 mediainfo 的樣本量一次再寫死，量測結果記在本票 Comments。
- **TMDB 沒有那一集片長時跳過**。mediainfo 失敗時照 §8.7「失敗不阻擋」，也跳過。
- 可疑的送審核，理由是新的 `ReviewReason`，說得出兩個片長。
- 手動送單與 RSS 走同一條檢查。

同票 14，檢查是純函式，M5 的 AI 結果也要過它。

## 驗收

- [x] 純函式單元測試：差太多、剛好在門檻內外、TMDB 沒片長、mediainfo 失敗（`tests/unit/test_parser_runtime.py`）
- [x] ~~一個 90 秒的 NCOP 被解析成正片 → 送審核~~ 改成「12 分鐘的 SP 被解析成第 11 集 → 送審核、理由說得出兩個片長」，90 秒的 NCOP 斷言它仍由分類器自動降成 extra（見 Comments）；片長對得上的照常入庫（雙向，`tests/integration/test_runtime_check.py`，手動送單的合併檔也一條）
- [x] `berth bench` 跑一輪，`auto_wrong` 不升（review 比例的變化記在 Comments）
- [x] 新理由的 zh-Hant 與 en 文案；plan §3.1 同步
- [x] lint、type、test 綠燈

## Comments

**與分類器的分工（2026-09-26 使用者拍板）**：`parser/classify.py` 本來就把 mediainfo 量到短於 5 分鐘的「正片」自動降成 extra（brief §6.2），所以票面的「90 秒 NCOP 被解析成正片」在現行程式碼裡到不了片長驗證。選項是保留分類器、片長驗證管 ≥ 5 分鐘（SP、OVA、合併檔）；另兩個選項（有 TMDB 片長時交給檢查、或兩者都做）沒選。整合測試因此改成 12 分鐘的 SP，90 秒那條斷言它仍自動成為 extra、照常入庫。每集 3 分鐘的短篇動畫會被分類器誤降成 extra 的舊問題不在本票（`classify.py` 的註解說「批次一致性會救回來」，實際上沒有這條路徑）。

**門檻量測**（`scripts/experiments/runtime_gap.py`，子代理做；AnimeTosho 的逐檔 mediainfo 對 `tests/fixtures/tmdb/` 的快照，8 部動畫、9 筆語料，批次種子被 AT 跳過的改抓同作品同集數的另一個發佈）：

| 類別 | n | 比例 | 差（秒） |
| --- | --- | --- | --- |
| 對得上的正片 | 87 | 0.94–1.03（p50 0.993） | −84 到 +41（p50 −10） |
| 兩集合併成一檔（相鄰兩集相加模擬） | 79 | 1.86–2.04 | +1288 到 +1560 |
| 真的量到的外傳（One Piece 兩支，若被當成正片） | 2 | 0.993 | −10 |

定成 `RUNTIME_SLACK = 180` 秒、`RUNTIME_RATIO = 0.15`，容忍 = 取大（等價於「差超過 3 分鐘**而且**超過 15%」）：正片兩個方向都留了約兩倍餘裕，合併檔差 7 倍以上。**已知盲點**：與正片一樣長的番外被當成正片它看不出來（上表第三列），那要靠標題或集名，不是片長。樣本只有動畫（AT 只收動畫）；一小時的劇靠比例那一邊（±9 分鐘）。沒量到真的 NCOP / PV（批次裡沒有或被跳過），那一類本來就歸分類器。語料裡 TMDB `runtime` 是 `null` 的集數 46.6%（5753 / 12353，長壽番居多），所以 `runtime_missing` 會常見。AnimeTosho 公告 2026 年 10 月初到中旬停止服務，原始資料快取在 `.local/experiments/cache/runtime_gap/`。

**`berth bench`**：172 / 0，high 0/84、medium 0/88 錯，review 81——與票 14 相同。語料沒有片長（`files[]` 只有大小），bench 也只跑解析器，所以片長驗證對它沒有作用；review 比例不變。

**沒有量到 mediainfo 時不記一筆**（票面只說跳過）：pre-plan 那一輪每一列都是 `None`，記的話預覽上每列都是雜訊；§8.7 本來就是「失敗不阻擋，只少一個訊號」。TMDB 沒有片長時照播出日比對的做法記 `runtime_missing`。

**只看劇集的集**：電影的片長在 `MediaSnapshot.runtime`，票面與 plan §11.4 說的是「那一集」，沒有做。

**UI 實跑**：演練情境 `rss-runtime`（`scripts/fake_setup_server.py`，mediainfo 替身讓第 11 集量到 12:05），playwright 登入 `skipper`、加 Mikan 聚合 feed、綁定《与你相恋》補舊集之後 `/review`：「要你決定」一份，抬頭「量到的片長與 TMDB 那一集差太多，多半是特典或合併檔被當成正片」，那一列留著 S01E11 與目標路徑、理由「mediainfo 量到 12:05，TMDB 上 S01E11 是 24 分鐘：差太多…」；其餘 11 集在「已入庫，等你看一眼」。en 同樣。截圖 `.local/screens/m3-15/review-{zh,en}.png`。

**S00 也比**（Spec 軸問是不是刻意的）：是。規則層只在檔名明說 `S00Exx` 時才對到第 0 季，而那時比的是 TMDB 上那一集自己的片長。芙莉蓮 `[7³ACG]` 那 11 個特典就是這種：字幕組的 `S00E01`–`E11` 每支都接近正片的長度，TMDB 的 S00 卻是 1–2 分鐘的「○○の魔法」短篇（`tests/fixtures/parser/README.md` 說這 11 筆「要做對得靠集名或片長比對」）。所以真實的那一包現在會停在審核，這是片長驗證想要的結果。

**code-review（對 `feafc27`）**：
- Standards 軸：沒有硬違規，6 條判斷題。修了 4 條：
  - `airing` 與 `runtime` 重複的 `_held` / `_noted` 收成 `parser.planner.hold` / `note`；
  - 按季找集改成 `MediaSnapshot.episode(season, number)`；
  - `_verdict` 的兩段 if 改成一張有順序的表 `_HELD_BY_CHECKS`；
  - `services/plan._checked` 改名 `_program_checks`。
  - 另外單元測試的容忍改成寫死的數字（原本是重算一次公式）；`test_air_date_check.TestManual.submit` 提成模組函式 `submit_manually`（原本是把測試類別當 helper 實例化）。
- 沒修的兩條：
  - mediainfo 替身在整合測試與 `fake_setup_server.py` 各寫一份。一邊是測試、一邊是演練工具，跨過去共用反而把兩者綁在一起。
  - `runtime_gap.py` 沒用 `lib.py` 的 `request`。一次性腳本，另有自己的 429 節流與快取。
- Spec 軸：規格都做到了。
  - 修了實驗 README 的敘述（原本寫量了 NCOP / SP 的落點，其實沒有）。
  - 補了 plan §4.2 的 `duration_s` 第二個消費者。
  - `schema.d.ts` 裡 `PlanEditedOut` 描述的換行是產生器照 HEAD 重跑帶出來的（上一張票沒重產），跟著進版控。

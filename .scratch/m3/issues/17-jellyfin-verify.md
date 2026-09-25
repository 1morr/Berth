# 17 — Jellyfin 回驗

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §2.4（`issues` 的型別與冪等鍵）、§3.2（`jellyfin_resolver`）、§8.2（`items`）、§11.4（「入庫前後的三道程式檢查」③）；brief §6.10、§9.1、§20.1、§20.9

## 做什麼

三道程式檢查的第三道，是**便宜的保險，不是主力**（brief §19 的 2026-09-24 更正）：它抓的是 Jellyfin 那邊的意外，例如兩份涵蓋範圍不同的正片被合成一集、檔案沒被認成正片。Berth 自己算錯的集數它抓不到。

- `jellyfin_resolver` 目前只用路徑找 item。找到之後多比三件事：Jellyfin 認到的季號、集號（多集檔是範圍），以及所屬 Series 的 `ProviderIds.Tmdb`，都要與帳本一致。
- 不一致就開一種**新的 Issue 型別**。加進 `issues.type` 與事件共用的封閉集合，冪等鍵用 `ledger_id`，plan §2.4 的型別數與冪等鍵表同步。`detail_json` 說得出兩邊各是什麼。
- Issue 的動作：至少要有「重新反查」（Jellyfin 重新掃描之後再比）。「照帳本 rematch」是否也要，實作時看 brief §9.1 的動作欄決定；「忽略」照其他型別。
- 條件解除（下一次反查一致了）時由系統收，`resolved_by = system`。
- reconciler 的 Jellyfin 那一方（M2 票 09 起重對主條目）順手也用同一個比對，不另寫一份。

新的 Issue 動作是命令，照票 05 標副作用等級。

## 驗收

- [x] 用 Fake Jellyfin 造三種不一致（季號、集號、Series 的 TMDB id），各開一件新型別的 Issue；一致時不開（整合測試，雙向）
- [x] 同一列連續反查兩次只有一件 `open`
- [x] 條件解除時系統收掉
- [x] `/issues` 畫得出這一種，動作按得到；zh-Hant 與 en 文案
- [x] plan §2.4、§3.2 同步；brief §9.1 的表加一列
- [x] lint、type、test 綠燈

## Comments

2026-09-26 實作：

- **動作只有「重新反查」**。「照帳本 rematch」不做：帳本是對的那一邊，rematch 改的是 Berth 的命名，修不到 Jellyfin 認錯的那一個（brief §9.1 的表已加一列）。「重新掃描媒體庫」也不給：掃描找的是新檔案，不重認已經認錯的。修法在 Jellyfin 裡（識別、把被併的那一份移出去），列上的「下一步」寫著。
- **新的 Issue 動作是命令**：沒有新的命令函式——沿用既有的 `relook`（`issues._relook`，可逆：只把帳本那一列排回反查）。`services/issues` 仍在 `BEFORE_M3` 豁免表，`resolve_issue` 沒有標記；M5 做登錄表時逐顆動作標（`ACTION_DELETES` 旁邊）。
- 截圖：`.local/screens/m3-17/`（1280 / 390 × zh-Hant / en），演練情境 `issues` 按「立刻對帳」就開出一件（替身 Jellyfin 把第一集認成 `S01E01-E02`）；`pnpm -C web e2e --project issues` 2 passed，log 看得到按「重新反查」之後下一輪反查仍不一致、重開一件。

code-review（Standards / Spec 兩軸）已修：CONTEXT.md 沒同步（硬違規，補了 Reconciler、Issue 十四種與「Jellyfin 回驗」一條）、收掉 Issue 的迴圈抽成 `issues.clear_by_system`（`close_settled` 與回驗共用）、過時的 docstring、`disagreement` 的位置取值改具名、`_works` 改名 `_ledger_tmdb`；補了兩條測試（多版本合併的次要版本比主條目、集指著查不到的 Series 算作品不一致）。未處理：

- **系統收的路徑比票面窄**：「重新反查」按下去時那一件就由使用者收掉（同 `jellyfin_item_unresolved` 的先例），之後若仍不一致開新的一件；所以 `resolved_by = system` 只發生在每日對帳、與 importer 把那一列重新排進反查（重新入庫、rematch）時。要讓「重新反查」等比完才收，得讓 `resolve_issue` 有一種「送出之後仍開著」的動作——畫面上按完那一列不會消失，另議。
- **「忽略」之後第二天對帳又開**：照其他型別（票面），但偵測是週期的，對「故意保留兩份不同範圍的正片」的人等於每天問一次。健康檢查那兩種的「條件持續期間忽略有效」（`health_issues._still_ignored`）是現成的做法，等有人抱怨再搬。
- `detail_json.differs` 的三個值（`season` / `episode` / `tmdb`）是裸字串，前端 `IssueRow.tsx` 的 `DIFFERS` 抄一份；沒有做成 `domain` 的 enum（判斷題：`detail_json` 其他型別也都是自由格式）。
- `TMDB 120089` 的前綴直接寫在 JSX 裡：機器字串，不翻譯。

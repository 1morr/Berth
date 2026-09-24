# 17 — Jellyfin 回驗

**Status:** ready-for-agent

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

- [ ] 用 Fake Jellyfin 造三種不一致（季號、集號、Series 的 TMDB id），各開一件新型別的 Issue；一致時不開（整合測試，雙向）
- [ ] 同一列連續反查兩次只有一件 `open`
- [ ] 條件解除時系統收掉
- [ ] `/issues` 畫得出這一種，動作按得到；zh-Hant 與 en 文案
- [ ] plan §2.4、§3.2 同步；brief §9.1 的表加一列
- [ ] lint、type、test 綠燈

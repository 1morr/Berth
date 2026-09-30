# 28 — 擁有者成立前的空窗：不能提早登入、目標不能被悄悄換掉

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 14、15 條）；brief §19（擁有者、擁有者鎖）；plan §9.3 第 1 點、§9.4；
`berth/api/gate.py`、`berth/services/auth.py`；票 18 的 `## Comments`

## 為什麼（2026-10-01 精靈實測，接管既有 E12，實測證實）

- **`/auth/login` 提早發 session。** `/auth/login` 永遠匿名（`berth/api/gate.py:41-49`），`sign_in` 只要
  `services.jellyfin.base_url` 非空就把帳密交給 Jellyfin（`berth/services/auth.py:67-80,148-169`），頁 1 一選 Jellyfin 就寫了
  base_url。實測：擁有者未成立時，bad-jellyfin-elsewhere 的非管理員 guest 拿到 200＋session、`/api/jobs` 200；管理員拿到
  admin、`/api/routes` 200。畫面上不會發生，直接打 API 會。
- **匿名改目標，帳密送到新位址。** 擁有者成立前 `POST /setup/services/jellyfin` 匿名開放（`gate.py:57-64`），
  `POST /setup/owner` 不帶位址、用當下存的那一台（`berth/services/setup.py:214-222`）。實測：頁 1 顯示 :58097 的登入表單時，
  另一邊匿名把目標改成 :48096 → 原頁送出的帳密打到 :48096，畫面仍寫 :58097。截圖 E12-01、E12-02。

## 做什麼

Jellyfin、Seerr、Home Assistant 的首次設定都是「誰先到誰建立」，這一點不改；要堵的是「提早能登入」與「目標被偷換」。

1. 擁有者成立前，`/auth/login` 一律拒絕（前端 `/login` 本來就導回 `/setup`）。
2. `POST /setup/owner` 帶上畫面當時測過的 `base_url` 與 ServerId（`/System/Info/Public` 的 `Id`，brief §20.15）；與存下的
   不同就 409，畫面說「Jellyfin 的位址在你填表時被換過，重新測試再送」。未初始化的 Jellyfin 也有 Id，同一條規則。
3. 兩個人同時成立擁有者（程式碼疑點：先檢查、再打網路、最後寫，沒有鎖）：寫 `setup.owner` 時在寫鎖內再確認一次沒有擁有者，
   後到的回 409 `owner_exists`。

## 驗收

- [ ] 整合測試：擁有者未成立時 `/auth/login` 拒絕（非管理員與管理員都是）；成立後照舊（雙向）
- [ ] 整合測試：`/setup/owner` 帶的 base_url／ServerId 與存下的不同 → 409、Jellyfin 沒被呼叫；相同 → 照舊成立
- [ ] 整合測試：兩個成立擁有者的請求交錯 → 只有一個成立，另一個 409
- [ ] vitest：409（目標被換）的人話與「重新測試」
- [ ] playwright 或 curl 對 `berth-existing` 重現 E12 的兩個步驟，都被擋下。附文字結果
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

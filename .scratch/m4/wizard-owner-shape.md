# 精靈前置段：Jellyfin 優先（M4 票 06 的 onboard shape）

**Status:** confirmed（2026-09-28，使用者確認三題，都照建議）；實作後 critique 加了一條：成立之後照 06d 停在「擁有者：名字」，按了才走

`/impeccable onboard` 對 `.scratch/m0/wizard-shape.md` §5、§8 前置列的改寫。慣例來源：Seerr（先連媒體伺服器，
它的管理員就是擁有者）、Jellyfin 自己的啟動精靈（建立使用者時密碼打兩次）。

## 任務與第一個價值

剛 `docker compose up` 的人要的第一個證據是：**「Berth 認得我，而且我知道之後拿什麼登入」**。舊的第 1 步
叫他替一個不存在的「Berth 帳號」取密碼，接既有 Jellyfin 時那組帳密在精靈結束後登不進 Berth。

## 前置段

```
前置 [擁有者 · 尚未 | 擁有者 · skipper] [服務 · 0/2 已判定]
```

1. **擁有者**（第 1 步）：工作面先找 Jellyfin（只讀，不需要門鎖），找到之後才給表單。
   - 套件內（`StartupWizardCompleted=false`，或 Berth 已經替它建過管理員）：「建立 Jellyfin 管理員」。
     帳號、密碼、再一次密碼（前端比對）。lede：Berth 沒有自己的帳號，這組就是之後登入 Berth 的 Jellyfin
     帳號，角色由 Jellyfin 決定。
   - 既有：「用你的 Jellyfin 管理員登入」，密碼一次；不是管理員就地說明被拒。
   - 找不到（未解決、逾時）：工作面先放連線表單（沿用第 2 步那一份，只有 Jellyfin 一列）。
   - 剖面「將會做什麼」：Jellyfin 位址、版本與判定；套件內寫「建立 Jellyfin 管理員 · 完成 Jellyfin 初始設定 ·
     建立 API key『Berth』」，既有寫「建立 API key『Berth』· 不改任何設定」；兩者都寫「不存下 · 你的密碼」。
   - 成功那一刻發 Berth session（與 `/login` 同一種 cookie），精靈從此要登入。
2. **偵測服務**（第 2 步）：只剩 qBittorrent 與 Prowlarr，其餘不變。

泊位板、泊位 1 之後的導覽不動。泊位 1（Jellyfin）套件內只剩建媒體庫；既有只剩列媒體庫與加 Berth 路徑
（登入與 API key 在擁有者那一步已經做完）。

## 決定

- **偵測留在第 2 步只探兩個**（不是每個泊位自己偵測）：改動最小，泊位由票 07、08 各自改。
- **套件內 qBittorrent / Prowlarr 的介面帳密在 07 之前不設**：第 1 步的勾選框拿掉，寫密碼的程式碼留著、
  改讀泊位自己的欄位（`SetupQbittorrent.web_ui_*`、`SetupIndexer.web_ui_*`；`SetupIndexer.login_password` 照舊是 Berth 上一次寫進 Prowlarr 的那一份），07 補上填它們的地方。
  這段期間 Berth 靠免密白名單照常運作，使用者自己打開 qBittorrent WebUI 只有容器 log 的臨時密碼。
- **密碼打兩次只在建立時**：登入既有 Jellyfin 打錯了 Jellyfin 會拒絕；建立時打錯了沒有人會告訴他。

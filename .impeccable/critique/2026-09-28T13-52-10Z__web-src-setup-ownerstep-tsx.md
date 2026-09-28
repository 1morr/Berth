---
target: 精靈第 1 步 擁有者
total_score: 31
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\setup\\OwnerStep.tsx"
target_fingerprint: "sha256:8517fcd65abc0bfe42ca05d9fdaa080933a8a9cdd79812bdc6b9b2b0bd59de97"
target_path: "C:\\Users\\Roxy\\orca\\projects\\MediaServer\\web\\src\\setup\\OwnerStep.tsx"
timestamp: 2026-09-28T13-52-10Z
slug: web-src-setup-ownerstep-tsx
---
# Critique：精靈第 1 步「擁有者」（M4 票 06）

Assessment A 與 B 各由一個隔離的子代理跑（A：設計評審；B：偵測器 CLI + 瀏覽器 overlay）。

## Design specificity
為 Berth 而生：纜繩、剖面、泊位板、四信號色；「找到 Jellyfin → 它的管理員就是擁有者」照 Seerr，建立時密碼打兩次照 Jellyfin 自己的啟動精靈。lede 直接回答「之後拿什麼登入」。

## Nielsen（31/40）
1 狀態可見 3｜2 真實世界 3｜3 控制 3｜4 一致 3｜5 錯誤預防 3｜6 辨識 4｜7 效率 3｜8 極簡 2｜9 錯誤復原 4｜10 說明 3

## 偵測器（B）
CLI：OwnerStep.tsx、SetupPage.tsx 皆 0。overlay：mixed 一條 `flat-type-hierarchy`（整頁 h1 / h2 都是 18px，精靈共用樣式）；◉ × 兩顆無名按鈕是 overlay 自己的（誤報）。390 無水平溢出。載入後焦點在 h2，Tab 跳過頁首語言鍵（StepFrame 既有行為）。

## 優先問題
1. [P1] 既有模式已找到的 Jellyfin 下仍攤著位址表單，兩份表單搶一個工作面；纜繩寫 compose 主機名、表單寫使用者的位址。→ 本票已修：找到之後收起（「換一台 Jellyfin」再打開），`probeEndpoint` 用使用者填的位址。
2. [P1] 390 寬 sticky 主按鈕遮住欄位（精靈共用的 STICKY_ACTION）。→ 未修，記在票 Comments。
3. [P2] 成功零確認，直接跳第 2 步。→ 本票已修：照 06d 停在「擁有者：名字」，按了才走。
4. [P2] 拒絕訊息在送出鈕下方、窄版在視口外。→ 本票已修：移到送出鈕上方。

## Persona 紅旗
新手：兩份表單不知道填哪一份（已修）。手機：sticky 鈕遮欄位（未修）。無障礙：role=alert、aria-live、標籤與 autoComplete 皆到位。

## 次要
owned 模式的主按鈕是 BerthNav 的版面，與其他回頭看的頁一致；建立模式沒有密碼規則提示（Jellyfin 本身不限）。

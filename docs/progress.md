# 進度

狀態：`todo` / `doing` / `done` / `blocked`。任務定義與驗收在 `docs/plan.md` §11，這裡只記狀態、閱讀指引與紀錄。「讀」欄是該任務開工前要讀的章節，其他章節按需讀。

## 任務板

### M0 骨架

| ID | 狀態 | 讀 | 備註 |
| --- | --- | --- | --- |
| T0.1 | todo | plan §0、§1、§10；brief §16.1、§16.2 | `.gitattributes` 已有；LICENSE 用 MIT；README 要含所有開發指令 |
| T0.2 | todo | plan §2；brief §8 | |
| T0.3 | todo | brief §20.6、§20.7；plan §5、§9.2 | 大。Windows bind mount 硬鏈接已於 2026-09-07 實測通過（brief §20.7），腳本化即可；Jellyfin 命名實測是第一優先，結果決定 plan §5 是否凍結 |
| T0.4 | todo | plan §8；brief §20.1、§20.2、§20.7 | 大。每個 adapter 一個子任務，各附 Fake 與契約測試 |
| T0.5 | todo | plan §6（auth）、§7；brief §11 | 第一個 UI：先 `/impeccable init`、`/impeccable hooks on` |
| T0.6 | todo | plan §9；brief §16.3、§16.4 | 大。精靈用 `/impeccable onboard`；先做套件內路徑，再做既有服務路徑 |
| T0.7 | todo | plan §9.1、§9.2；brief §16.1 | |
| T0.8 | todo | plan §3.2（health_checker）、§9.5 | |

M0 驗收：brief §17 M0 列。

### M1 手動全流程

| ID | 狀態 | 讀 | 備註 |
| --- | --- | --- | --- |
| T1.1 | todo | plan §8.3；brief §10、§20.3 | |
| T1.2 | todo | plan §8.4；brief §20.7（Prowlarr） | |
| T1.3 | todo | plan §3.1、§8.1；brief §5 | |
| T1.4 | todo | plan §3.2、§3.3；brief §5.2、§20.2 | |
| T1.5 | todo | plan §4、§5；brief §6、§7、§20.4 | 大。先寫 fixture 與 harness，再逐階段實作 |
| T1.6 | todo | plan §3、§8.2；brief §5、§7、§20.1 | 大 |
| T1.7 | todo | plan §7；brief §13 | 每頁 `shape` → 實作 → `critique` |
| T1.8 | todo | plan §10 | |

M1 驗收：brief §17 M1 列。

### M2 – M4

範圍與驗收見 plan §11.3–§11.5。開工前先在此拆成任務並填「讀」欄。

## Session 紀錄

| 日期 | 任務 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-09-07 | 文件 | brief、plan、CLAUDE.md、progress.md 完成並 commit | T0.1 |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- （尚無）

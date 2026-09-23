# 11 — 【研究】大媒體庫量測（超門檻就做分段取）

**Status:** done

**Blocked by:** 09（reconciler 要走整個媒體庫，補齊十種之後才有東西可量）

**讀:** plan §3.2（`reconciler` 那一列末句）、§6（inventory 群組）、§11.3 的決定 2；brief §20.8；`docs/research/library-browsing.md` §2、§3、§6

## 做什麼

M1.5 留下來的成本問題，一次量完。用 `mattpocock-skills:research` 或 `prototype`，實驗腳本留在
`scripts/experiments/`（plan §10：一次性但保留腳本，下一次換版本要重量）。

**要量的五件**（同一個一次性 Jellyfin 環境，跑完即刪）：

1. `library_index` 的整份清單（reconciler 每一輪都要走一次）
2. 不帶 `parentId` 的 `/Items?hasTmdbId=true&fields=ProviderIds`（Media 詳情的觀看區在用）
3. `/Items` 帶整份 `MediaSources`（多版本顯示在用）
4. 「待審 / 對不到」篩選後的牆**帶觀看狀態**的代價——現在那一份是 `enableUserData=false`，
   卡片的 `watch` 是 `null`（票 14 會想把它畫出來）
5. **被刪掉的 Jellyfin 帳號** `GET /Users/{id}` 回什麼（M1.5 票 01 驗過停用的，沒驗過刪除的）

**門檻寫死在這張票上**（決定 2，拆票時不決定要不要快取）：

> **1,000 部的媒體庫上 `GET /inventory/{id}` p95 > 1 s，或 reconciler 走完一輪 > 10 分鐘，
> 就做分段取；否則不做快取。**

**超門檻時，分段取的實作就在這一票做**（使用者 2026-09-22 拍板）。不做快取——M1.5 的經驗是
網址帶 `tag` 才敢長快取，而這幾支的答案是「現在的狀態」。

結論回寫 brief §20.8 並連結研究文件。

## 驗收

- [x] 五件各有實測數字（筆數、位元組、p50 / p95），環境與資料量說得出來（1,000 部怎麼造的）——
      `docs/research/large-library.md` §0、§1、§4
- [x] 實驗腳本留在 `scripts/experiments/`，可重跑，起停一次性容器——`large_library.py` +
      `large_library_berth.py`；**1,000 部沒有一輪從頭跑到尾**（這台機器滿載時 Python 與 .NET 都 segfault，研究 §0），
      數字由 `--keep` / `--reuse` / `--stages` 分段補量
- [x] 對照門檻給出判定：超了哪一條、沒超哪一條，白紙黑字——研究開頭的判定表
- [x] 超門檻的那幾支**做了分段取**，量測後 p95 回到門檻內（貼前後數字）；沒超的明說不做並說明
      為什麼不順手做——**改法不是分段取**（使用者 2026-09-23 認可，偏差見 progress.md）：`GET /inventory` 的 3.4 s
      在 `_survey` 的二次方分組，修成一次分組之後 p95 0.66–0.68 s；對帳 27–31 s 沒超，不做的理由在研究 §3
- [x] 被刪掉的帳號那一項有結論，寫回 brief §20.8（停用與刪除兩種行為並列）
- [x] 結論摘進 brief §20.8 並連結 `docs/research/`；推翻既有做法時同一個 commit 改文件並在
      progress.md 記一行
- [x] 一次性容器與 volume 已刪除（貼 `docker ps -a` 與 `docker volume ls` 的過濾結果）：
      `docker ps -a --filter name=berth-exp-large: []`、`docker volume ls --filter name=berth-exp-large: []`
      （image 與 network 也刪了）
- [x] lint、type、test 綠燈——ruff / format / lint-imports（6 kept）/ mypy（270 files）/ `pytest` 2213 passed；
      前端沒動，`pnpm gen:api` 重產零差異

## Comments

code-review（`74e886c` 起）沒有處理的幾條，都是判斷題：

- **Standards**：實驗腳本裡有幾段重複（`load_config` + `create_engine` 四次、`sample` 與 `attempt` 的重試、
  `deleted_account` 抄了 `sign_in`），查詢參數是從 adapter 手抄的——adapter 改了會靜靜脫節，下一次重量時先對一次。
  腳本直接呼叫 `services.inventory._survey` / `_routes`（私有），改名時腳本會壞。一次性量測腳本，不為它們抽共用。
- **Standards**：`AccountDisabledError` 現在也涵蓋「刪除」，名字與意思不再一致。對外的 `account_disabled` 不能改；
  內部類別改名牽動 8 個檔案，這一票沒做。
- **Spec**：`reuse` 那一輪有兩個長尾（4c 200 部的 848 ms、`limit=500` 的 8.8 s），同一段時間 Jellyfin 被重啟過，
  研究文件當環境噪音處理。在穩定的機器上重量一次才分得清。
- 已處理：`args: Any` 改 `argparse.Namespace`；契約測試不再在測試內分支；`_found` 的 `params` 改選填；
  `create_library` 的空字串哨兵改 `None`；**刪除的判定收窄到只認 `Users/{id}` 的 404**（`UserViews` 的 404 可能是
  位址設錯，不該把人登出，另加一條測試與雙向變異）；研究文件的數字範圍重算、沒有證據的句子改寫或補上出處。

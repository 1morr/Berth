# 09b — 逐檔那一列自己也收起來

**Status:** done

**Blocked by:** 09

**讀:** 票 09 的 `## Comments`（「留著、沒有做的」第一條）；`.scratch/m1.5/long-lists-shape.md`；
`.scratch/m1.5/media-detail-shape.md` §3–§4

## 做什麼

票 09 把三份長清單收成分組，但**逐檔那一列沿用了原本的樣子**（拍板時如此決定），所以展開一組之後仍然
一個檔案三到四行。票 09 的 Comments 已經寫明下一步該做什麼，這一票做它：

- **組的摘要說過的，逐檔列不再重複**。「檔案與版本」的組摘要已經說了處置、蓋到哪幾集、帳本與 Jellyfin 的
  計數；計劃的組鍵本身就是「處置 × 季 × 信心 × 待確認」，四格在組裡必然相同。
- **路徑與理由收進逐檔列自己的展開區**。留在外面的是認得出這一筆、而且要拿來掃的那幾格。
- 來源檔名（`rel_path`）**留在計劃那一列的摘要上**：一包 torrent 裡有字型、有海報、有 readme，少了它那幾列
  的「略過」長得一模一樣。

順帶兩件在比對 worktree 版本時抓到的：

- **`SeasonsPanel` 抽出來，帶 `key={media.id}`**。「只看缺集」的 state 現在在 `SeasonList` 裡，而
  `/media/$mediaId` 是同一條路由——在作品之間換頁時元件不重掛，篩選會跟著上一部帶過來。
- **`fake_setup_server.py` 的 `--port` 沒有真的生效**：演練用的 torrent 下載連結寫死 `127.0.0.1:8484`，
  所以 `--port` 一改，送單就回 `source_unavailable`。

## 驗收

前後對照都在演練情境 `long-lists`（真 TMDB、芙莉蓮 39 個檔案真的入庫、1280×900）上量，同一份資料、同一個
後端，只把 `web/src` 換成改動前的版本再量一次。

- [x] 「檔案與版本」展開一組之後的高度（芙莉蓮 28 個檔案，前後對照）
      —— **2,824 → 1,032 px**；逐檔那一列 **80 → 16 px**。
- [x] `/jobs` 展開一組之後的高度（同一包 39 項計劃，前後對照）
      —— **3,655 → 863 px**；逐檔那一列 **118 → 16 px**。28 個檔案現在一屏看得完。
- [x] 逐檔資訊仍然拿得到：路徑、Tags、理由展開得到
      —— 收在列自己的 `<details>`：「檔案與版本」是「Tags」與「目標」+ 完整路徑，計劃是「目標」+ 目標路徑
      與解析器的英文理由。收起時內容留在 DOM 裡（組展開之後 Ctrl+F 仍找得到路徑）。
- [x] 組摘要沒說死的仍然逐列說得出來（帳本對不上、Jellyfin 找不到、組裡混合的狀態）
      —— 規則是「**上面說過而且是常態值的才省略**」：`status === 'ok'` 與 `presence === 'found'` 省略，其餘照說。
      「還在掃描」帶下一次查詢時間、「試了 N 次」帶次數，這兩個組的計數說不出來，所以留在列上。
      電影不分組、上面沒有人說，所以那幾格全部留著。
- [x] 「只看缺集」在換作品時回到全部
      —— 季表連工具列抽成 `SeasonsPanel`，詳情頁以 `key={found.id}` 掛上。測試先暖快取再換作品（**沒有讀取中的
      空檔才重現得了**：冷快取會經過 loading、元件自己就重掛了）。
- [x] `fake_setup_server.py --port <非 8484>` 送單成功
      —— 以 `--port 8383` 實跑：送單 → 計劃 → 入庫 → 反查全部走完，39 個檔案入庫、Job `imported`。
      修法是 `DEMO_PORT` + `demo_url()`，`main()` 在建情境之前設定它。
- [x] 前端測試涵蓋以上每一條
      —— `FileEntry.test.tsx`（收起時路徑不可見、展開才有；**外層 `<details class="group">` 展開時提示仍說「展開」**）、
      `MediaDetailPage.test.tsx`（逐檔列的外與內、例外仍逐列說得出、電影不分組時每一格自己說、換作品回到全部）、
      `JobPlan.test.tsx`（摘要是季集 + 來源檔名、處置與信心不重複、目標與理由展開才有）。
- [x] playwright 實跑：1280 / 390 × 深淺兩主題，頁面層級橫向捲動 0
      —— 四種組合量「檔案與版本」與 `/jobs` 的計劃（組展開 + 逐檔列展開），**橫向捲動全部 0**。
      鍵盤：焦點到逐檔列的 `<summary>` → Enter → 展開、提示翻成「收起」、`:focus-visible` 為真。
      截圖在 `.playwright-mcp/t09b-*.png`（不進版控）。
- [x] lint / type / test 全綠並貼指令輸出（見下）

## 指令輸出

```
$ uv run ruff check .          → All checks passed!
$ uv run ruff format --check . → 304 files already formatted
$ uv run mypy                  → Success: no issues found in 217 source files
$ uv run lint-imports          → Contracts: 6 kept, 0 broken.
$ uv run pytest -q             → 1550 passed, 4 deselected in 151.51s
$ pnpm -C web typecheck        → (tsc -b --noEmit，無輸出)
$ pnpm -C web lint             → (eslint .，無輸出)
$ pnpm -C web format:check     → All matched files use Prettier code style!
$ pnpm -C web test             → Test Files 27 passed (27) / Tests 422 passed (422)
```

## Comments

- **`ExpandHint` 的 `group-open:` 在巢狀 `<details>` 裡會誤判**：Tailwind 的 `group-open:` 匹配的是任一個帶
  `group` 的祖先，不是最近的那一個。逐檔列長在 `JobRow`（`JobRow.tsx:71` 帶 `group`）與季的收合區裡面，所以
  逐檔列自己一定要走 `ExpandHint` 的受控 `open`，不能用 CSS 那一種。票 09 已經為了組長列踩過同一個坑。
- **不做**：`long-lists` 情境在 Windows 上 S00 入庫失敗（目標路徑超過 260 字元）不是這一票的事，README 的情境表
  與 progress.md 都已經寫明要用 `--config-root` 指短路徑，容器裡是 Linux 不會踩到。

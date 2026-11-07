# 11b — 修「可以看了」真服務 e2e 的穩定紅

**Status:** done

**Blocked by:** —

**讀:** 票 11 的 Comments（三次斷言、main nightly 的兩次紅、resolver 線索）；`tests/e2e/`（含 `stack.py`）、`pipeline/`、`services/notify.py`、`docs/development/e2e.md`

## 為什麼

票 11 跑真服務 e2e（`pytest -m e2e`）三次，都是 27 passed／1 failed，紅的一直是
`test_an_rss_hit_tells_the_crew_it_is_downloading_then_ready_to_watch`（「可以看了」600 秒內沒到）。
main 的 nightly e2e 在 2026-11-05、11-06 也紅在同一條，兩次都早於 M5.6 的任何 commit（M5.6 從 11-07 08:43 UTC 起），
`pipeline/` 與 `services/notify.py` 自 v0.5.0 起沒改過——所以不是這批造成的，但它是穩定紅，會擋住票 11 的
「`pytest -m e2e` 綠」。

## 做什麼

1. **先分清是產品的問題還是測試的問題**：重現那一條（`pytest -m e2e -k an_rss_hit` 這類最小指令），
   把失敗現場留住——要留容器與 volume 就在本分支暫改 `tests/e2e/stack.py` 的收尾（暫改不進 commit）或手動
   compose；讀服務 log、通知排程與 resolver 的流程，寫出「哪一步沒有發生、為什麼」。
2. **先有會紅的 repro 才修**：repro 寫進本票 Comments（指令、失敗的斷言、失敗現場在哪）。只把 600 秒拉長而
   說不出原因的不收。
3. 修法依根因落在產品或測試：產品就同輪補測試與文件（`docs/development/e2e.md`；行為對使用者可見才動
   CHANGELOG），測試就修測試並說明為什麼不是產品的問題。
4. 修完那一條**連跑三次都綠**，再跑一次整套 `pytest -m e2e`。
5. 一併把票 11 需要的重跑做掉：修完回報協調者，票 11 的 session 會 merge main、重跑 `pytest -m e2e` 與最後一輪
   全部檢查，然後才補勾「`pytest -m e2e` 綠」並封存（那一勾不在這張票）。

## 驗收

- [x] 會紅的 repro 寫在票的 Comments（指令、失敗斷言、失敗現場位置）
- [x] 根因寫清楚，且分清是產品還是測試
- [x] 修法有測試或實跑證據；沒有只放寬逾時
- [x] 紅過的那一條連跑三次都綠，整套 `pytest -m e2e` 也綠
- [x] 全部檢查、pytest 綠；`docs/progress.md` 已更新

## Comments

- 2026-11-07 協調者：票 11 的真服務 e2e 三次都紅在同一條；依協調者規則（穩定紅一律插修復票）插這張，
  排在票 11 封存之前。票 11 已把三次斷言、nightly 的兩次紅與 resolver 線索寫在它的 Comments。

### 重現：指令、失敗的斷言、失敗現場

- **指令**（同票 11）：`uv run --env-file .env python -m tests.e2e.stack`。
- **失敗的斷言**：`test_5_m4_notify.py::test_an_rss_hit_tells_the_crew_it_is_downloading_then_ready_to_watch`
  的 `_arrives("the ready-to-watch notice", …, 600)`；11-05 的 nightly 則是它下一句
  `_arrives("the admin's ready-to-watch notice in Chinese", …, 120)`。紅的記錄：票 11 的三次本機實跑
  （11-07 12:35／13:10／13:53 UTC）、main nightly `42310408822`（11-06）、`42131140979`（11-05）、
  `40131851229`（10-24，同一句 600s）。這條測試 10-23 才加入（`5edc058c`），所以是**自加入起就間歇性紅**。
  （票頭說的「票 11 的 Comments」在 `1morr/t11` 上，不在這個 worktree 的檔案裡：`git show
  92674d69:.scratch/m5.6/issues/11-m5.6-acceptance.md`；本 worktree 的分支還沒 merge 它。）
- **失敗現場**：CI 的容器 log（`gh run view <id> --log`，`docker compose logs` 那一段）。
  - **11-05**：`BOSUN` 23:54:28 收到「可以看了」而且比對到了；管理員在 23:53:28 收到兩則，送出正好
    是排下之後 5 分鐘（只有 `queue_ready` 等 5 分鐘：`downloading` 不等、`waiting` 等 10 分鐘）——
    所以那是「可以看了」，但那一句斷言照樣逾時：內文不是逐字的 `S01E06`。
  - **11-06**：23:36:19 一輪送 4 則（`admin`、`BOSUN` 各 2 則，兩部作品），`BOSUN` 到 600 秒為止
    一則都比對不到（斷言本身保證了這一點；內文裡沒有逐字的 `S01E06`）。
  - **11-07 本票實跑**：`up` 之後這台機器的 jellyfin／qbittorrent 十秒內就健康，精靈跑得比它們快，
    `test_1` 的冷啟動閘門（`len(rounds) > 3`）直接紅在 setup（與本票無關）；之後在 `up` 之後
    重啟那兩個容器讓閘門真的走到，再跑整條流程（見文末三次）。

### 根因：測試的比對太窄，產品行為是對的

- 「可以看了」的內文是 `notify.describe_spans` 組的季集範圍；同一人、同一作品、同一 Route **5 分鐘內**
  的幾筆在寫入時合成一則（`notify.MERGE_WINDOW`，M4 票 125）。這是既有、有測試的行為：
  `tests/integration/test_notify.py::TestMerge::test_two_jobs_within_five_minutes_are_one_message`
  斷言內文是 `S01E01–E03`。
- 這套 e2e 的第 2 輪（第 5 集）與第 3 輪（第 6 集）只差 1–3 分鐘。第 2 輪那一則有沒有在第 3 輪提出時
  還在合併窗裡，看的是 Jellyfin 反查的時序；命中時內文是 `S01E05–E06`，測試的
  `"S01E06" in description` 永遠對不上，於是等到 600 秒逾時——通知其實送到了（11-05 的 log 就是）。
- **觀察**：本票一輪沒合併的實跑（2026-11-07 14:37–15:13 UTC，28 passed）的 DB 裡，那一則是
  `episodes [[1, 6, 6]]`（`S01E06`），所以比對得到。合併時的形狀（`[[1, 5, 6]]`）是**推論**，來自
  `notify._merged` + `_collapse` 與 `TestMerge` 對內文的斷言，不是本輪 DB 的觀察——本機四輪的時序
  都沒讓第 5 集那一則排進待送表（`wired` 之前沒人訂「可以看了」，`queue_ready` 回 0）。
- 也排除過「真的沒排／沒送」的另外兩條路：`_announce` 沒寫「ready notification not queued」的 log
  （`queue_ready` 回 0 的三條路之一會寫），而 CI 11-05 的 log 直接顯示管理員收到了那兩則。
- 不是 `pipeline/`／`services/notify.py` 的問題，也不該放寬逾時。

### 修法（測試）

- `tests/e2e/harness.py` 加 `episodes_in(description)`：把內文**第一段**展開成 `(季, 集)` 集合
  （`S01E05–E06`、`S01E01, E03`、`S02E01`、`E100` 都認得；第二段是 `[在 Berth 打開](…)` 連結，不讀），
  與 `tells(embed, title, episode)`：標題相同、內文涵蓋這一集。
- `tests/e2e/test_5_m4_notify.py` 三處比對改用 `tells`：第 6 集（`BOSUN` 英文、管理員中文）與第 4 輪的
  第 7 集。第 6 集那兩則是根因；「正在下載」那兩則**不是**合併窗造成的，但同一輪同一部作品的多筆也會
  合成範圍（`downloading._content` 收整輪的 Job、`_render` 用 `describe_spans`），所以一起改。
- 單元測試 `tests/unit/test_e2e_harness.py`（8 條：單集、合併範圍、同季省略季號、換季、連結那段、
  讀回產品的 `describe_spans`（含 `E100`）、合併過的 embed 走 `tells`、電影空字串；突變：把範圍展開
  拿掉三條會紅）。
- `docs/development/e2e.md`〈e2e〉那一句補上合併與比對方式的說明。

### 綠：修正後連跑三次

`-k an_rss_hit` 單獨跑不起來（第 3 輪要的兩個 Feed 由 `test_4_` 建），所以每輪都是整套
`uv run --env-file .env python -m tests.e2e.stack`。這台機器的服務十秒內就健康，`up` 之後先
`docker compose restart jellyfin qbittorrent`，精靈醒來時它們還在啟動，冷啟動閘門真的走到（repo 的
測試沒有改，第一次沒重啟時紅在 setup 的就是它）。

這是 **code-review 修完之後的最終程式碼**上的三次（前一批三次在重構前，數字 `34:21`／`21:58`／`34:50`；
重構只是把比對抽成 `harness.tells`，行為相同，仍重跑一組）。

| 輪 | 結果 |
| --- | --- |
| 1 | `28 passed in 2089.04s (0:34:49)` |
| 2 | `28 passed in 2090.92s (0:34:50)` |
| 3 | `28 passed in 2057.66s (0:34:17)` |

三次跑完的 DB 裡那一則都是 `[[1, 6, 6]]`（`S01E06`）——這台機器的時序沒撞到合併窗，所以三次綠
證明的是「紅過的那條在現在的程式碼上跑得過、沒被改壞」。合併分支本身由
`tests/unit/test_e2e_harness.py` 守（`tells` 吃一份合併過的 embed、`episodes_in` 讀回
`describe_spans` 的真實輸出）。

### 檢查（2026-11-08）

- `uv run pre-commit run --all-files`：13 個 hook 全過。
- `uv run pytest -n auto`：**5812 passed、1 skipped**（95 秒；新的一條就是 `tests/unit/test_e2e_harness.py`
  的合併 embed）。
- 全套 `pytest -m e2e`：上面三次。

### Code-review（2026-11-08，`/code-review` 對開工時的 `230e95b4`）

- **Standards**（3 條硬的、4 條取捨，全部已處理）：
  - 票〈檢查〉的 `pytest -n auto` 寫成「見下一列」、沒有輸出 → 補上 `pytest -n auto` 的實測數字。
  - 票沒有 code-review 紀錄 → 這一節。
  - `_SPAN` 只吃兩位數集號，產品的 `f"{episode:02d}"` 第 100 集是 `E100` → 改 `\d+`，單元測試補 `E100`。
  - `season = 0` 替產品不會寫的「開頭裸 `E07`」留了條路 → 改成 `None`，沒有季號就斷言失敗。
  - 三處同樣的比對、`(1, 6)`／`(1, 7)` 散落 → 抽成 `harness.tells` 與 `SIXTH_EPISODE`／`SEVENTH_EPISODE`。
  - `docs/development/e2e.md` 同一個條目重複講「合併 5 分鐘」→ 第二處改寫成「合併窗」。
- **Spec**：
  - 「三次綠沒走到合併分支」成立（本機時序）：票裡改成明說，合併分支由 `tests/unit/test_e2e_harness.py`
    的 `tells` 吃一份合併過的 embed、加上產品的 `TestMerge` 守；三次綠證明的是紅過的那條在最終程式碼上跑得過。
  - 「下載那兩處是多做」不成立：同一輪同一部作品的多筆也會合成範圍（`downloading._content` 收整輪的 Job），
    已在〈修法〉寫明。
  - 「`[[1, 5, 6]]` 看不出是觀察還是推論」「11-06／10-24 沒貼送出內文」→ 票裡已改成推論並寫出依據與
    已排除的另外兩條路。
  - 「票頭引用的票 11 Comments 不在這個 worktree」→ 已在〈重現〉註明它在 `1morr/t11`（`92674d69`）。
  - `episodes_in` 的 `assert` 在產品格式改變時是整個測試錯誤、不是靜靜地不匹配 → 刻意保留：搭一條讀回
    `describe_spans` 的單元測試，改格式會先在單元測試紅。

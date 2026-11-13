# 里程碑：開工與驗收

里程碑開工的 session 與做驗收票的 session 照這份做。其餘的票照 `AGENTS.md`〈每個 session 的流程〉。

## 開工

入口是使用者在新 session 下 `/to-tickets docs/roadmap.md 拆 <里程碑> 的票`。依序做完三步，第 3 步 commit 後才算完成：

1. **spec**：把 roadmap 裡它的那一節，依最新的 brief、plan 與上一個里程碑的結果細化成 `.scratch/<里程碑>/spec.md`，段落為〈目標〉〈範圍〉〈共同規則〉〈驗收〉〈票序〉。roadmap 那一節的內容搬進 spec，標題留著，內文縮成一行連結，里程碑表的狀態改成「進行中」。文件不足以寫出 spec 時，問使用者並補進文件。
   - 〈驗收〉底下有 `### 使用者試`：使用者親手用才知道的事（看不看得懂、手機上按不按得到、試用機上的實際結果），每條寫明怎麼啟動、試什麼。沒有就寫「無」和理由。
2. **票**：照 `/to-tickets` 提出切法，使用者同意後寫票，每張票寫明「讀：plan §x、brief §y」與驗收條件。最後一張固定是驗收票 `NN-<里程碑>-acceptance`，被其他所有票擋。
3. **收尾**：票序寫回 spec〈票序〉，progress.md 加一列 session 紀錄，「下一步」寫第一張票的指令，commit。

`tests/unit/test_scratch_specs.py` 守：spec 的五段與「使用者試」、roadmap 那一節縮成一行連到 spec、驗收票存在。

## 驗收票

依序做，前一步成立才做下一步：

1. spec〈驗收〉逐條對到一條測試或一次實跑，對照表記在票的 Comments，缺的補上。
2. 從里程碑開工的 commit 起跑 `mattpocock-skills:code-review`。
3. 各票 Comments 沒處理的發現逐條歸位：修掉、延後（寫進 roadmap 接手的那個里程碑的小節，沒人接的進〈不排里程碑〉）或不做。
4. **使用者試**：把啟動方式與 spec `### 使用者試` 的清單給使用者，progress.md 的「下一步」寫 `等使用者：試用 <里程碑>`，結束 session。使用者回覆後在新 session 接著做這張票：
   - 不滿意的項目各開一張修復票（`NNb-<slug>`，排在驗收票之前），修完再請使用者試。
   - 使用者要 agent 代測：照做，並在 `docs/decisions.md` 記一條（使用者定），寫明哪幾項沒有人親手試過。
   - 使用者說可以了才往下。
5. **封存**：照 progress.md〈寫法與封存〉，把這個里程碑的 session 紀錄與 `docs/decisions.md` 裡它的決定搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明遺失 0；roadmap 里程碑表的狀態改成「已驗收（日期），封存於 …」。封存後 session 紀錄加一列 `<下一個里程碑> 準備`，「下一步」寫 `/1morr:checkpoint <這個里程碑>`；沒有下一個里程碑就留空，只在對話告訴使用者。
6. 整理 CHANGELOG。要不要發版、push 先問使用者。

完成條件：spec〈驗收〉每一條都有證據或使用者的回覆；每個發現都歸了位；progress.md 與 decisions.md 只剩下一個里程碑的。

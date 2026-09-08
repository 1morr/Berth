# 01 — 動漫季集來源定案（TVDB 研究）

**Status:** done

**Blocked by:** 無 —— 可立即開工

**讀:** brief §10、§20.3、§20.6（最後一條）；plan §2.2、§4.3、§4.4

## 做什麼

brief §10 的【研究】「TVDB 作為 anime profile 的季集來源」定案。抽 10 部動漫（要涵蓋 split-cour、
連續兩季、長篇累計編號、劇場版接續正篇這幾種形態），量化字幕組實際使用的編號換算到三種來源的
失敗率：TMDB 季集、TVDB default(aired) season、TVDB absolute。以數字決定 anime profile 的季集
來源要不要換。

這張票**沒有產品程式碼**，但它決定 `media` 表的欄位與 `map_episode` 的形態，所以排在所有會碰
`media` 或解析器的票之前。採用 TVDB 的形態已在 brief §10 寫好：Media 主鍵維持 `tv:<tmdb id>`，
`media` 加 `tvdb_id` 與 `episode_source`，只有 `anime` profile 的 Route 用 TVDB 編號並要求該媒體庫
裝 TVDB 插件。

用 `mattpocock-skills:research`，輸出放 `docs/research/`。

## 驗收

- [x] 10 部動漫的樣本清單與挑選理由寫在 `docs/research/`，每一部附三種來源的季集對照表
      （`docs/research/anime-episode-source.md` §1、§2；樣本固定在 `scripts/experiments/anime_sample.json`）
- [x] 三種來源各自的換算失敗率有數字（TMDB 8.0% / TVDB aired 7.6% / TVDB absolute 7.6%，
      7,833 筆真實釋出），失敗案例逐條寫出是哪一種形態造成的（§6.1–§6.3）
- [x] 決定寫進 brief §10（【研究】改成【決定】：**維持 TMDB**）並附理由；§20.6 最後一條已劃掉
- [ ] 若採用 TVDB：plan §2.2 補 `media.tvdb_id` / `episode_source`、§4.3 的 `MediaSnapshot` 與 §8 補
      TVDB adapter；票 03、05、06 依此修訂並在票上註明改了什麼
      → **不適用**，量測結果是維持 TMDB
- [x] 若維持 TMDB：brief §10 寫明放棄理由與弱點對策（絕對編號換算 + review），票 03、05、06 不動
      → 放棄理由已寫（0.4 個百分點 vs 三道實作牆）。**弱點對策沒有照票寫的「絕對編號換算 +
      review」留著，而是依實測改寫**：絕對編號換算只影響 16% 的釋出、TMDB 在那一段只錯 4.4%，
      真正的弱點是檔名沒有季號（佔失敗的 91%）。**票 03、05、06 也不是「不動」**——見下一條
- [x] **偏離票的部分（推翻上一條的「票 03、05、06 不動」）**：03 與 05 解除 blocked-by（機械操作）；
      05 補「季號的全形羅馬數字」；06 補「篇章名 → 季號」「最終季 → 最後一季」「第二部分 /
      Part.2 當 cour 偏移」。理由是這三條是量測指出的**主要**槓桿（合計佔失敗的九成），
      不寫進票就會連同這份研究一起被忘掉。已記進 progress.md 的「偏差與決定」
- [x] 資料來源與查詢方式可重跑：`scripts/experiments/anime_episode_source.py`（含 `--self-test`
      與 `--discover`），指令在根 README，方法在研究文件 §3、§4
- [x] `docs/progress.md` 的「偏差與決定」已記一行

## Comments

- **這張票沒有產品程式碼**，所以沒有跑 `/tdd`；換算器的正確性靠腳本內建的 `--self-test`
  （三個手算過的樣例：TMDB 併季、行銷季號 ≠ 播出輪次、劇場版佔掉一個 absolute）。
- **量測方法比原本設想的重**。票寫的是「量化字幕組實際使用的編號換算到三種來源的失敗率」，
  但「字幕組寫的 12 到底是哪一集」本身就要先解決。中途換過三次錨點（正篇序位 → TVDB
  absolute → 發佈時間校準），前兩次都會把模型自己的偏差算成 provider 的差異。最終方法與
  三道校準閘寫在研究文件 §4.1。
- **未量到的部分**（研究文件 §8）：Mikan 沒有 2013 年以前的番組，所以進擊的巨人 S1、
  航海王與柯南的早期 cour 沒有樣本；nyaa.si 在本機被 DNS 攔截，英語字幕組完全沒納入；
  9,392 集因為校準證據不足（BD 合集、補檔、小組）被捨棄。
- **順帶推翻 brief §20.3 兩處**：TMDB 的合併政策比原記載激進得多（連獨立的連續季也在併），
  而 TVDB 的 absolute 會把 OVA 與劇場版也編號（所以 absolute ≠ 正篇第幾集）。兩處已改。
- **plan §4.4 的 180 天門檻第一次有數字支持**（180 天 8.0% vs 60 天 9.7%），已寫進 plan。

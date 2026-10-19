# 83c — 照作品名搜：三個字以下的中文名也要算「對得上名字」

**Status:** done

**Blocked by:** None — can start immediately

**讀:** 票 83b 的 Comments 與 `.scratch/m4/search-typed-filter-shape.md`〈已知的代價〉；`berth/parser/title.py` 的 `mentions`、`_MIN_CONTAINED`、
`typed_fits` / `_contains_words`；`berth/services/search.py` 的 `_judge`；brief §20.20

## 為什麼（2026-10-14 票 83b 實跑發現）

《無間道》照作品名搜（`Infernal Affairs`、`無間道` 兩個查詢）：dmhy 的 `無間道 III [国语中字.高清无水印]`、`[无间道I][国语中字…]` 這類只寫中文名的
發佈全歸「名字對不上」，預設看不到。原因是 `mentions` 的長度下限 `_MIN_CONTAINED = 4` 算的是正規化後的字數，「無間道」「无间道」只有三個字，
整個名字被略過（下限是為了拉丁字的 `Up` 出現在半數發佈名裡）。

票 83b 在自己打關鍵字那條路上已經用 `_contains_words`（有 CJK 不設下限、不到四字的拉丁字要整詞相等）解決同一件事，但票面規定照作品名搜的六類不改，
所以這裡留著。

## 使用者拍板（2026-10-19）

> **改定（同日，第 5 點抽查之後）：門檻改成 3 個字。** 兩字名抽查新進「符合」的 25 筆全是無關的發佈（見 Comments），
> 使用者選「三個字起」。下面這段是原本的兩字版，留著看理由；做什麼與驗收已照三字改。

**含 CJK 的名字至少 2 個字才拿來比（包含即可）**；1 個字的照舊略過。拉丁字維持現狀（不到
`_MIN_CONTAINED` 不比）。理由：一個字的中文名（`她`）幾乎什麼發佈名都含，會把無關的發佈判成對得上；
兩個字以上已涵蓋《無間道》《寄生》這類。一字名的作品照作品名搜仍看不到，要改用自己打關鍵字（83b 那條路）。

## 做什麼

1. **`mentions`**（`mattpocock-skills:tdd`）：CJK 名字的下限從 `_MIN_CONTAINED`（4）改成 3（原為 2，見上方改定）；拉丁字照舊。
   不改 `_contains_words`（自己打關鍵字那條路，83b 定的「CJK 不設下限」維持）。
2. **`partial_title`**（衍生劇判斷，`title.py` 找「包住某個名字」的 `wider` 那一段）：CJK 用同一個下限 3。
   不跟著改的話，`無間道前傳` 這類會被 `mentions` 判成對得上、卻不被 `partial_title` 標成衍生劇，直接混進正片。
3. **不動** `_compare`（`matches()` 的計分，RSS 與入庫用的那一支）：那是自動決策路徑，這張票只改搜尋的粗篩。
4. 改的是解析器模組：照規矩跑 `berth bench`，`auto_wrong` 不得上升；前後數字寫進 Comments。
5. 用實際語料抽查：至少《無間道》與一部兩字中文名的作品照作品名搜，看「對得上」裡有沒有明顯無關的發佈。
   兩字名誤判明顯偏多時，停下回報（附例子），不要自行改門檻。

## 驗收

- [x] 《無間道》照作品名搜時 `無間道 III [国语中字]` 不再是「名字對不上」；pytest
- [x] 一、兩個字的中文名照舊不算對得上，三個字的算；pytest 各一條（改定前寫「一個字不算、兩個字算」）
- [x] 名字只對上一部分的三字中文名（改定前寫「兩、三字」）（例如 `無間道前傳` 之於《無間道》）被 `partial_title` 標成衍生劇；pytest
- [x] `berth bench` 前後比較寫在 Comments，`auto_wrong` 不上升

## Comments

### 第一輪（2026-10-19，兩字門檻，停在第 5 點）

已做第 1–4 點：`_long_enough`（含 CJK 兩個字起、拉丁字照 `_MIN_CONTAINED`）給 `mentions` 與 `partial_title` 共用；
`_compare`、`_contains_words` 沒動。測試：`test_parser_title.py::TestShortChineseNames`（三字、兩字、一字、短拉丁字、
兩條衍生劇、自己不算部分）與 `test_search.py::test_a_three_character_chinese_name_fits_a_title_search`，改動前都紅（stash 驗過）。

**berth bench**：改動前後輸出逐字相同——`overall 904 files · auto_correct 255 · auto_wrong 0 · review 84`；
high 0/112、medium 0/143 wrong（`mentions`、`partial_title` 不在 bench 的路徑上）。

### 語料抽查（第 5 點）：兩字名誤判明顯偏多，照票面停下

做法：dmhy RSS（`share.dmhy.org/topics/rss/rss.xml?keyword=`，每個查詢 3 頁）＋ TPB（apibay，電影類）的真實發佈名，
查詢照預設的英文名與原名，去重後逐筆丟 `services.search._judge`，改動前後各跑一次比歸類。沒經 Prowlarr，分類是同一支。

| 作品 | 改動前「符合」 | 改動後「符合」 | 新進「符合」的 | 其中是這部作品的 |
| --- | --- | --- | --- | --- |
| 《無間道》（三字） | 2 | 4 | 2 | 2（`無間道 III [国语中字.高清无水印]`、`[无间道I][国语中字…]`） |
| 《英雄》2002（兩字） | 60 | 81 | 21 | 0 |
| 《活著》1994（兩字） | 4 | 8 | 4 | 0 |

《英雄》新進「符合」的例子：`[VCB-Studio] 英雄教室 / Eiyuu Kyoushitsu …[Fin]`、`剧场版 我的英雄学院：You're Next [1080p]`、
`[時雨初空] 落第骑士英雄谭 BDRip …`、`[沸班亚马制作组] 龙珠超 超级英雄 […]`、`【ASMR】救救我，英雄先生…♪`。
《活著》：`[The ARC-V Project][遊戲王ARC-V][SCALE.6 活著的真實感]`、`[假面骑士Saber][第43章][激战 活着的意义]…`、
`(一般コミック) [Tiv] ぼくラはミンナ生きテイル！/我们都还活着 全3卷`。

`partial_title` 擋不下它們：多半沒有季集記號或年份（沒有片名那一段就不判），有的英雄二字在片名中段。
另外《英雄》有 262 筆從「名字對不上」移到「不是電影」（預設看不到，但按鈕上的數字會變）。

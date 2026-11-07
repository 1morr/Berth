# 06 — `find_in_library` 給集數

**Status:** done

**Blocked by:** 01

**讀:** spec〈範圍〉C4；研究文檔 §4 C4；plan §6〈inventory〉、§8.2〈找作品與集：`items()`〉；brief §12

## 為什麼

Jellyfin 沒刮到 TMDB id 的作品，`media_read_media` 找不到，模型只知道「媒體庫裡有一部叫這個名字的」，不知道使用者有哪幾集，就沒辦法判斷缺什麼。

## 做什麼

1. 劇集的命中多一格 `episodes`：用 Jellyfin 的季號與集號，依季寫成範圍，不連續的地方斷開（例如 `S01E01–E05, S01E07–E12`）。電影沒有這一格。
2. 輸出或工具說明註明這是 Jellyfin 的編號，不是 TMDB 的。
3. 只替命中的劇集讀集數；請求數有上界（命中數有上限，fake client 計數）。走這個人看得到的媒體庫，門禁不變（brief §12）。
4. Jellyfin 讀集數失敗時，那一筆的 `episodes` 是空的並說明原因，整次呼叫不失敗。

## 驗收

- [x] 劇集命中帶依季的範圍，中間缺一集時會斷開；電影沒有 `episodes`（測試）
- [x] 請求數有上界（fake client 計數）；讀集數失敗不拖垮整次呼叫
- [x] 工具說明寫明是 Jellyfin 的編號
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- 形狀：`episodes` 是一季一個字串的 dict（`{"1": "1-5, 7-12"}`），不是整串 `S01E..` 文字。模型要回答「有沒有第 7 集」，dict 比 parse 字串直接；與 `media.read_media` 給模型的集數範圍同一個寫法。那個寫法與「多集檔算它蓋到的每一集」這條規則由 `domain/episodes.py` 的 `number_ranges` / `season_ranges` 提供（原本只在 `agent_tools`，這次搬出來共用）。沒有季號或集號的集不算進範圍，但會在 `episodes_note` 說有幾集數不出來。
- 電影的 `episodes` 是 `None`，交給模型前由 `MODEL_VIEWS["inventory.find_in_library"]` 拿掉這一格；劇集讀得到集數時也一併拿掉空的 `episodes_note`。
- 同一部劇被幾個名字對到只讀一次集數；一次查詢最多讀 `FIND_EPISODE_READS`（20）部，超出的那一格是空的、`episodes_note` 說沒讀（60 個名字全中的極端情形不至於一次送出數百支請求）。要讀的是「從允許清單上的媒體庫清單（`index`）讀到的劇」，`JellyfinAccess` 因此也把那幾部 id 記成可問集數的（與 `locate` 確認過的同一條閘門；清單本身先擋媒體庫）。
- 讀失敗只影響那一部（清單已讀到、集數這一支失敗時）：`JellyfinUnreachableError` 的原文、`ItemNotVisibleError` 的說明寫進 `episodes_note`，整次呼叫照常回；另一部劇的集數照樣有。
- code-review 未採的兩項（都是取捨）：`episodes`／`episodes_note` 沒有合併成一個小型的值物件（兩個欄位已經由一個建構點寫明，還不需要型別）；`_compact_find_in_library` 就地 `pop`（那份是 `to_jsonable_python` 剛產生的，不動到別人的資料）。
- 2026-11-07 決定（使用者查證後定）：`series_episodes` 也接受從允許清單媒體庫清單（`index`）讀到的 id。理由：那份清單只列這個人看得到的媒體庫，而且 `series_episodes` 仍帶 `userId`（Jellyfin 對無權的劇回 404），兩層都還在；NextUp 仍只認 `locate`。brief §20 那一句與 §12 已同輪改，實作不動。

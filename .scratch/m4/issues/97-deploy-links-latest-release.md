# 97 — 部署檔改用固定網址：README 指「最新 Release」的附件，發版不必再改連結

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/development.md`〈發版〉；`.github/workflows/release.yml`；`tests/unit/test_readme_docs.py`；`docs/guide/upgrading.md`、`docs/guide/requirements.md`〈Unraid〉；M4 票 71（「Release 頁不附檔案」的由來）

## 為什麼

README 兩份與 `requirements.md` 的部署檔連結寫死版號（`raw.githubusercontent.com/1morr/Berth/v0.2.4/deploy/...`），每次發版都要改。忘了改有 `test_readme_docs.py` 擋，但仍是每版一次的手工。使用者（2026-10-13）要固定網址。

採用 Immich 的慣例：它的安裝說明寫 `wget https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml` 與 `example.env`。`releases/latest/download/<檔名>` 永遠轉到最新正式版的附件，預發佈不算「最新」。連結指 release 而不是 `main`，所以照樣不會讓 compose 比 image 新。

這推翻票 71 的「Release 頁只放說明、不附檔案」。使用者先前在意的是 zip，兩個純文字附件不在此限。

## 做什麼

1. `release.yml` 建 Release 時附兩個檔：`deploy/docker-compose.yml` 以 `docker-compose.yml` 上傳，`deploy/.env.example` 以 `example.env` 上傳。GitHub 會改名開頭是 `.` 的附件，開工時先查證這一點（REST API「Upload a release asset」的說明），把結論與來源補進 brief §20。
2. README 兩份、`requirements.md` 的連結改成 `https://github.com/1morr/Berth/releases/latest/download/docker-compose.yml` 與 `.../example.env`，`curl` 那兩行也是。說明裡「這一版的副本」的措辭跟著改。
3. `upgrading.md`：要固定某一版的人，把 `latest/download` 換成 `download/v<版號>`，照這個寫法說明。
4. Unraid 那段原本叫人打開連結、複製貼上。附件點下去是下載，要改成「下載後打開，全選複製貼上」之類的說法，實際走一次確認可行。
5. `test_readme_docs.py`：
   - 改守「部署檔連結一律是 `releases/latest/download/` 加上那兩個檔名」。
   - 另守「`release.yml` 上傳的正是這兩個檔、這兩個名字」。
   - 照全域規則，在測試檔內做雙向變異驗證。
6. `development.md`〈發版〉拿掉「換連結」那一步，改寫發完要確認 Release 頁有兩個附件，以及 `latest/download` 拿得到。
7. **已發布的 v0.2.4 補上附件**：`gh release upload v0.2.4`，上傳 v0.2.4 tag 底下的那兩個檔，名字照上面。這樣合併之後新連結馬上有效，不必等下一版。上傳前確認檔案取自 tag，不是 main。

## 驗收

- [ ] 合併後，匿名 `curl -fsSL` 新的兩個連結拿得到 v0.2.4 的那兩個檔，內容與 tag 底下的相同，貼輸出
- [ ] `test_readme_docs.py` 的新規則有雙向變異驗證；README 兩份標題層級與連結仍一致
- [ ] brief §20 補上附件命名的查證結果（附來源）；development.md、upgrading.md、requirements.md、CHANGELOG 同步；progress.md「偏差與決定」記一行（推翻票 71）
- [ ] 全部檢查、pytest 綠

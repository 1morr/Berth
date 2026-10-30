# 開發指令：發版

發版流程。其他開發指令見[主檔](../development.md)的索引。

### 發版

部署只有兩個檔：`deploy/docker-compose.yml` 與 `deploy/.env.example`（brief §19 E4）。每一版的 Release 把它們附成
`docker-compose.yml` 與 `example.env`（M4 票 97；開頭是 `.` 的附件名會被 GitHub 改掉，brief §20.17），README 連到
`releases/latest/download/<附件名>`，永遠是最新正式版的附件，發版不必改連結；`tests/unit/test_readme_docs.py` 守著
連結的寫法與 workflow 附上的兩個檔。發一版（例如 `0.2.5`）：

1. `CHANGELOG.md` 的 `[Unreleased]` 改成 `[0.2.5] - <日期>`，寫清楚從上一版升級要注意的；`pyproject.toml` 的
   `version` 改成 `0.2.5`，`uv lock`。
2. 合進 `main`、全部檢查與 test 綠燈之後 `git tag v0.2.5 && git push origin v0.2.5`。預發佈（`v0.3.0-rc1`）一樣要先有
   `## [0.3.0-rc1]` 那一段，否則 image 推完、Release 才失敗。

`v*` tag 上 `.github/workflows/release.yml` **先過閘門**：對這個 tag 的 commit 跑完整的 CI（`ci.yml`），再跑真服務的
e2e（`e2e.yml`，約 50 分鐘），兩個都綠了才推 image 到 GHCR（`:0.2.5`、`:0.2`、`:latest`），再建 Release：
說明是 CHANGELOG 的 `## [0.2.5]` 那一段（相對連結換成這個 tag 底下的 blob），找不到那一段就失敗；附件取自這個 tag。
任何一段紅了，什麼都不發佈：修好之後推新的 patch 版 tag，不要移動已經推出去的 tag。整個 Release run 約一小時，
進度在 Actions 的那一個 Release run 裡（CI 與 e2e 是它的子 job）。`tests/unit/test_release_gate.py` 守著這個順序。
`-rc` 標成 prerelease，不動 `:latest`，`releases/latest` 也不會指到它。發完確認：

- Release run 綠（含 ci 與 e2e 兩段），Release 頁有 `docker-compose.yml` 與 `example.env` 兩個附件。
- 匿名 `curl -fsSL https://github.com/1morr/Berth/releases/latest/download/example.env` 拿得到，內容與 tag 底下的
  `deploy/.env.example` 相同（`docker-compose.yml` 同樣比一次）。預發佈不會是 `latest`，把 `latest/download` 換成
  `download/v0.3.0-rc1` 再比。
- 匿名查 GHCR `:latest` 與 `:0.2.5` 是同一個 digest。

發版那次 push 到 `main` 的 CI，以及 tag 的 release run 還在跑時，不要再 push `main`：ci.yml 的 `concurrency`
（`cancel-in-progress: true`，同一個 ref 一組）會取消 `main` 上進行中的 CI run，那一版就少了一次完整的綠燈。
release.yml 沒有 `concurrency`，不會被取消，但等它綠了再動 `main` 比較清楚。

使用者那一面（tag 的意思、升級步驟、固定在某一版）在 [`guide/upgrading.md`](../guide/upgrading.md)。

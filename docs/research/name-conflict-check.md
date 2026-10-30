# 名稱衝突檢查

從 design-brief §20.5 搬來（原文不改字）。

### 20.5 名稱衝突檢查

以 tavily basic 搜尋 GitHub / npm / PyPI / Docker Hub / App Store，非窮盡商標檢索。

| 名稱 | 評級 | 證據 |
| --- | --- | --- |
| Berth | 可用（已定案） | 精確比對（2026-09-07）：GitHub 無同領域專案，最接近的是 macOS SSH 客戶端 xinghelee/Berth（31★）；PyPI `berth` 是 2017 年停更的打包工具；npm `berth` 已標記 deprecated；Docker Hub 有 `berth/` 組織（舊 OpenStack 容器化專案，已停）。本系統以 `ghcr.io/<owner>/berth` 發佈，不需要這三個註冊名。 |
| Lading | 可用 | 未找到同名軟體專案 |
| Cleat | 可用 | 未找到同名軟體專案 |
| Longshore | 可用 | 僅人名 |
| Mooring | 可用 | 未找到同名軟體專案 |
| Keelhaul | 可用 | 僅文化典故 |
| Wharf | 輕微 | 數個小型不活躍專案（iver-wharf 等） |
| Gangway | 輕微 | VMware 已封存的 k8s OIDC 工具 |
| Drayage | 輕微 | 小型 Docker volume 遷移工具 |
| Dockhand | **衝突** | 現役自託管 Docker 管理工具，5.8k★，同為 homelab 領域（[Finsys/dockhand](https://github.com/Finsys/dockhand)） |
| Stow | **衝突** | GNU Stow |
| Quay | **衝突** | Red Hat Quay |
| Tally | **衝突** | TallyPrime 會計軟體與同名自託管記帳 App |
| Stevedore | **衝突** | OpenStack stevedore（PyPI plugin 載入套件） |

# 錄製回應

adapter 契約測試的輸入（plan §1.2、§10）。每個檔案都是**對真服務錄下來的回應原文**，
不是手寫的假 payload——手寫的 payload 只會證明程式與自己的想像一致。

## 來源

2026-09-07（票 05），用 `deploy/docker-compose.yml` 起一套乾淨的服務錄的：

| 檔案 | 來源 |
| --- | --- |
| `jellyfin/system-info-public.setup-pending.json` | `lscr.io/linuxserver/jellyfin`（10.11.11）第一次啟動，`GET /System/Info/Public` |
| `jellyfin/system-info-public.configured.json` | 同一台跑完 `POST /Startup/Complete` 之後的同一支端點 |
| `qbittorrent/app-version.txt` | `lscr.io/linuxserver/qbittorrent`（v5.2.3），從白名單內的 IP 打 `GET /api/v2/app/version` |
| `qbittorrent/app-webapiversion.txt` | 同上，`GET /api/v2/app/webapiVersion` |
| `qbittorrent/app-version.forbidden.txt` | 同一支端點，從**不在**白名單的宿主打，回 403 |
| `prowlarr/ping.json` | `lscr.io/linuxserver/prowlarr` 第一次啟動，`GET /ping` |
| `prowlarr/indexer.empty.json` | 同一台，`GET /api/v1/indexer`（還沒加任何索引站） |
| `prowlarr/indexer.configured.json` | 由同一台的 `GET /api/v1/indexer/schema` 的 Nyaa.si 條目裁出常用欄位並補上 `id`。**不是**整包錄下來的：容器連不出去（TLS 被中斷），`POST /api/v1/indexer` 建不起來 |
| `../prowlarr/config.xml` | 同一台的 `/config/config.xml`，`<ApiKey>` 換成同形狀的假值 |

## 規則

- 檔案裡不放真的秘密。`config.xml` 的 API key 是拋棄式容器產的，仍然換成 `0000…0001`。
- 要重錄就重跑一次上面的來源，不要手改內容——改過的 fixture 就不再是證據。
- 新增服務或版本時開新檔案，不要覆寫既有的：舊版本的行為差異正是契約測試要守的東西
  （qBittorrent 4.4 與 5.x 的差異在票 08）。

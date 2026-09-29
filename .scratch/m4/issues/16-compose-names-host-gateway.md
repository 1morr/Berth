# 16 — compose：套件容器名加 `berth-` 前綴、Berth 連得到宿主（host-gateway）

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（不依賴 15；建議排在 15 之後）

**讀:** brief §16.3（compose profiles 那一條）、§16.4〈容器裡的 `localhost`〉、§20.14；plan §9.1、§9.5〈連線位址〉；`.scratch/m4/wizard-manual-choice-decision.md`〈compose 裡沒拿掉的套件內服務〉

## 為什麼

- **撞名**：同一台主機上的既有容器大多就叫 `jellyfin` / `qbittorrent` / `prowlarr`、用 8096 / 8080 / 9696 / 6881。
  使用者接既有服務卻忘了從 `COMPOSE_PROFILES` 拿掉套件內那一個時，撞名的那個套件內容器起不來（社群報告其他容器
  照常起，**沒實測過**）。使用者拍板套件容器名改成 `berth-*`（brief §19 2026-09-29 ③）。
- **Linux 上 Berth 連不到宿主上的既有服務**：`host.docker.internal` 只有 Docker Desktop 內建；Linux 要 compose 的
  `extra_hosts: ["host.docker.internal:host-gateway"]`（brief §20.14）。15、17 的提示叫使用者填這個名字，它得真的解得到。

## 做什麼

1. `deploy/docker-compose.yml`：三個套件服務加 `container_name: berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`
   （`berth` 維持）；**compose 服務名與 profile 名不變**——Berth 以服務名（compose 網路上的 DNS 名）連它們，
   `bundled_targets` 與 `.env` 的 `COMPOSE_PROFILES` 都不必改。
2. `berth` 服務加 `extra_hosts: ["host.docker.internal:host-gateway"]`。在 Docker Desktop 上確認明寫這一條不會蓋掉
   它內建的解析（容器內 `getent hosts host.docker.internal` 仍指到宿主）。
3. 所有寫死容器名的地方跟著改：真服務 e2e harness（`docker logs` / `docker exec` 之類）、README 的疑難排解指令、
   `scripts/`；`C:/Users/Roxy/berth-lab`（repo 外）的 compose 與 `reset.sh` 同步。
4. `.env.example` 在 `COMPOSE_PROFILES` 旁寫明：接既有的哪個服務就拿掉哪一個 profile。
5. **實測撞名撞 port**：宿主上先起一個叫 `jellyfin`（與一個佔 8096）的容器，`docker compose up -d` 看哪些容器起得來、
   錯誤訊息長什麼樣。腳本留在 `scripts/experiments/`（CLAUDE.md：下次換 Docker 版本要重量），結果與版本寫回
   brief §20.14 那一條「待實測」。容器名改了之後撞名這一半應該消失，撞 port 仍在——精靈的「既有」說明要不要多說
   一句，照實測結果決定並寫進 plan §9.3。
6. CHANGELOG：已經部署的人 `docker compose up -d` 之後三個容器以新名字重建（設定在 bind mount 上，不受影響）；
   自己寫過 `docker exec qbittorrent …` 的要改名字。

## 驗收

- [ ] `docker compose config` 裡三個套件容器名是 `berth-*`、`berth` 有 `extra_hosts`；單元測試守著（與 `tests/unit/test_deploy_ports.py` 同一類，檔內雙向變異：拿掉前綴會紅、改無關的格式不紅）
- [ ] Docker Desktop 上 `berth` 容器內 `host.docker.internal` 解得到、連得到宿主上的一個 port（貼指令輸出）；Linux 有環境就一併量，沒有就在 Comments 記「Linux 未實測」
- [ ] 撞名 / 撞 port 的實測腳本在 `scripts/experiments/`，結果與 Docker 版本寫進 brief §20.14
- [ ] 真服務 e2e 全綠（harness 改名之後）；`berth-lab` 同步後 `reset.sh bundled` 起得來
- [ ] README、`.env.example`、CHANGELOG 同步；plan §9.1 若與實作有出入一併改
- [ ] lint、type、test 綠燈

## Comments

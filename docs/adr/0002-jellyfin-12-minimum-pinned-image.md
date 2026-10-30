# 只支援 Jellyfin 12 以上，套件內 image 釘在 12.1 線

只支援 Jellyfin 12 以上。同日稍早定的「兩條版本線都支援、13.0 發佈才拿掉 10.x」被使用者改掉，為了降低複雜度：Jellyfin 12.0 起原生把同一季資料夾裡同一個 `S/E` 的檔案合併成一集的多個版本，Berth 因此不裝 MergeVersions，精靈的 MergeVersions 步驟、既有服務按鈕、resolver 的合併觸發與任務 id 整段移除。既有 Jellyfin 低於 12 時，精靈與健康檢查紅燈，說出目前版本並附升級注意（brief §20.9），不往下做。

套件內 Jellyfin image 釘在 12.1 這條線（linuxserver `version-12.1ubu2604`）：跟得上 12.1 的修正與重建，pull 時不會默默跨到下一版；實測過新版才調高，`docs/guide/upgrading.md` 寫升級步驟（先備份 Jellyfin 的 `/config`、升級後完整掃描）。2026-09-29 使用者再確認版本下限維持 12.0。

## Consequences

已知代價：從 10.11 升到 12 有遷移失敗的 open issue、舊客戶端要升級、binhex（unRAID）與 QNAP 社群套件還沒有 12，那些使用者要先升級才能接 Berth。

來源：brief §19 舊列「Jellyfin 支援版本」「套件內 Jellyfin image」（原文在 `docs/archive/m1.md`）。

# `/review` 只列入庫決定，Issue 只在 `/issues`

Review Queue 與 Issue 原本同時出現在 `/review`。兩頁的分工改成：`/review` 是「入庫要人決定」，`/issues` 是「Berth 與外界對不上」（對照 Sonarr 的 Queue / Interactive Import 對 Health）。`/review` 不再列 Issue，原位留一行「另有 N 件待處理」。

權限：Review Queue、Issue 的動作、rematch、刪除範圍、手動對帳一律只有 admin（brief §11）；`user` 的 Job 停在 review 時畫面說「等管理員審核」。

來源：brief §19 舊列「M2 後的全面審查」②、「審核、修正與刪除的權限」（原文在 `docs/archive/m2.md`）。

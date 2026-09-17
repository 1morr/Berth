# e2e 的種子影片

`tests/e2e/payload.py` 用這兩個檔案造出三包發佈裡的每一支影片（plan §10、票 15）。

| 檔案 | 內容 |
| --- | --- |
| `seed.mkv` | Matroska，320×180 黑畫面，1 fps，330 秒，H.264 |
| `seed.mp4` | 同上，MP4 |

**330 秒是刻意的**：短於 5 分鐘的正片會被分類器降成特典（`parser/classify.py` 的
`SHORT_FEATURE`），而 e2e 要走的是「正片自動入庫」那一條路。檔案小到可以進版控，所以 CI 不必裝
ffmpeg，info hash 也每一次都一樣。

2026-09-15（票 12 的驗收）以 ffmpeg 產生：

```bash
ffmpeg -v error -f lavfi -i color=c=black:s=320x180:r=1 -t 330 \
  -c:v libx264 -tune stillimage -pix_fmt yuv420p -f matroska -y seed.mkv   # mp4 同上，-f mp4
```

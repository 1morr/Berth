# 通知管道是 Discord bot 私訊，用收件人自己的語言寫

M4 只做 Discord，不做 Telegram，也不做頻道 webhook：頻道裡每個人看得到全部，破壞媒體庫權限；M7 要收訊息與按鈕非 bot 不可。代價是管理員要在 Discord 開發者後台建一個 bot、每人填自己的 user ID（事實在 brief §20.23 與 `docs/research/discord-notifications.md`）。

通知用每個人自己的語言寫：收件人不在瀏覽器上，後端原本不知道誰用哪個語言，所以存 Discord ID 的那一刻記下當下的介面語言（`users.notify_language`），送出時照它組字。這是後端第一個自己組人話的地方（`services.notify`），句子 zh-Hant 與 en 並列。考慮過但沒選：全站一個語言、只用繁中（英文使用者會收到中文）。

來源：brief §19 舊列「通知的管道是 Discord bot 私訊」「通知用每個人自己的語言寫」（原文在 `docs/archive/m4.md`）。

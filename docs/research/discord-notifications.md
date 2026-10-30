# Discord 通知：webhook、bot 私訊、互動的查證

查證日期：2026-10-21。範圍：Berth 要從單一 Python 程序（FastAPI + httpx，無 discord.py）推通知到使用者手機（M4，只送），以及 M7 要收訊息與按鈕確認。

來源規則：只用 Discord 官方。API 事實取自官方文件 repo `discord/discord-api-docs`（`main` 分支，`developers/**/*.mdx`，即 discord.com/developers/docs 的原始檔），逐檔下載後 grep，下文連結用站上 URL；使用者側操作取自 Discord Help Center（support.discord.com）；成熟產品取自 GitHub 原始碼。查不到的標「未查到」，不以記憶補。

來源基準 URL（下文簡稱）：

- Webhook Resource：https://discord.com/developers/docs/resources/webhook
- Message Resource：https://discord.com/developers/docs/resources/message
- User Resource：https://discord.com/developers/docs/resources/user
- Rate Limits：https://discord.com/developers/docs/topics/rate-limits
- Opcodes and Status Codes：https://discord.com/developers/docs/topics/opcodes-and-status-codes
- Gateway：https://discord.com/developers/docs/events/gateway
- Interactions Overview：https://discord.com/developers/docs/interactions/overview
- Receiving and Responding：https://discord.com/developers/docs/interactions/receiving-and-responding
- Components Reference：https://discord.com/developers/docs/components/reference
- Using Message Components：https://discord.com/developers/docs/components/using-message-components
- Application Resource：https://discord.com/developers/docs/resources/application
- OAuth2：https://discord.com/developers/docs/topics/oauth2

## 1. Webhook（頻道 webhook）

| 事實 | 結論 | 來源 |
|---|---|---|
| 定位 | "a low-effort way to post messages to channels"，不需要 bot user 或 authentication | Webhook Resource 開頭 |
| 建立方式 | 使用者在 Server Settings > Integrations 點 "Create Webhook"，可設名稱、頭像、目標頻道，然後複製 webhook URL | Help Center「Intro to Webhooks」https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks 、「Server Integrations Page」https://support.discord.com/hc/en-us/articles/360045093012-Server-Integrations-Page |
| 另一種取得方式 | OAuth2 scope `webhook.incoming`：使用者在授權畫面選頻道，token response 內含 webhook 物件（需要 redirect URI，Berth 無公開網址時不適用） | OAuth2 〈Webhooks〉 |
| 請求 | `POST /webhooks/{webhook.id}/{webhook.token}`；token 在 URL 路徑上。至少要有 `content`、`embeds`、`components`、`file`、`poll` 之一 | Webhook Resource〈Execute Webhook〉 |
| query | `wait`（true 才回傳建立的 message，預設 false 回 `204 No Content`）、`thread_id`、`with_components` | 同上 |
| body 欄位 | `content`（最多 2000 字元）、`username`、`avatar_url`、`tts`、`embeds`（最多 10 個）、`allowed_mentions`、`components`、`flags`（只能設 `SUPPRESS_EMBEDS`、`SUPPRESS_NOTIFICATIONS`、`IS_COMPONENTS_V2`）、`thread_name`、`applied_tags`、`poll` | 同上 |
| `@mention` 使用者 | 在 `content` 放 `<@user_id>`。webhook 與 interaction 的 `allowed_mentions` 預設只 parse `users`（`{"parse":["users"]}`），所以 `<@id>` 預設就會被解析；`@everyone` / `@here` 需要 `MENTION_EVERYONE` 權限；roles 需 role 設為 mentionable。文件建議對含使用者字串的內容明確設 `allowed_mentions` | Message Resource〈Allowed Mentions Object〉 |
| 手機是否會推播 | 文件只說 mention 會觸發通知、`SUPPRESS_NOTIFICATIONS` 會關掉推播只留 badge、且「使用者可在 app 內自訂通知設定，可能只收到 badge 而無推播」。是否一定推播取決於使用者的頻道 / 伺服器通知設定，文件未保證 | 同上 |
| 被 mention 的人須在伺服器內才有效？ | 未查到明文 | - |
| 送 DM | 文件未明言「不能」；webhook 物件綁 `channel_id`、執行端點只有 `/webhooks/{id}/{token}`，且整份文件把 webhook 定位為「post messages to channels」。結論：webhook 沒有 DM 的途徑（由資料模型推得，非明文） | Webhook Resource |
| 按鈕 / components | 分兩種。非 application 擁有的 webhook（使用者在頻道手動建的）：必須加 `?with_components=true`，且 "cannot send interactive components"，只能送非互動元件；application 擁有的 webhook 可送全部 components | Webhook Resource〈Execute Webhook〉註 `*` |
| 按鈕按下後誰收到互動 | 互動送給「擁有該 message 的 application」（文件的 Interactions 都是對 app 投遞，見第 3 節）。手動建的 webhook 沒有 application，所以也不存在可接收的對象，這與它不能送互動元件的限制相符。Link button（`style: 5`、帶 `url`）不會對 app 送出 interaction，但文件沒有明講「Link button 屬於非互動元件、可在手動 webhook 使用」，此點未查到 | Components Reference〈Button〉 |
| 速率限制 | 官方 Rate Limits 頁沒有列出 webhook 的具體數字（未查到）。頁面說「不要寫死限制，要解析 response header」；top-level resource 含 `webhook_id` 或 `webhook_id + webhook_token`，也就是每個 webhook 各自一個 bucket | Rate Limits |
| 429 形狀 | HTTP 429、JSON body：`message`、`retry_after`（float，秒）、`global`（bool）、`code?`；header：`Retry-After`、`X-RateLimit-Limit/Remaining/Reset/Reset-After/Bucket`、`X-RateLimit-Scope`（`user` / `global` / `shared`）；global 時另有 `X-RateLimit-Global` | Rate Limits〈Exceeding A Rate Limit〉 |
| 失效 webhook | 回 404 就不要再用，重複嘗試會被暫時限制；`10015` = Unknown webhook。invalid request（401/403/429，`shared` scope 的 429 除外）每 10 分鐘超過 10,000 次會被 Cloudflare 暫時封 IP | Rate Limits〈Invalid Request Limit〉、Opcodes and Status Codes |

重點：webhook URL 本身就是憑證（token 在路徑），Berth 要把它當 secret 存、log 時遮蔽。

## 2. Bot 私訊

| 事實 | 結論 | 來源 |
|---|---|---|
| 純 REST 能否送訊息 | 官方 bots 概覽寫「Connect to the API using the Gateway for real-time events, the HTTP API for REST operations, or both」，即 REST 是獨立的合法用法。**「bot 必須至少連過一次 gateway 才能發訊息」這個要求，在官方文件中未查到**（Gateway 文件只說 Identify 是「sending or receiving most Gateway events」的前置，談的是 gateway 事件，不是 REST）。要確認就需實測，不能由文件斷言。**2026-10-21 實測（M4 票 121）：從沒連過 gateway 的 bot 照樣私訊得到**（brief §20.23） | https://discord.com/developers/docs/bots/overview 、Gateway〈Identifying〉 |
| 開 DM channel | `POST /users/@me/channels`，body `{"recipient_id": "<snowflake>"}`；已存在就回傳既有的 DM channel | User Resource〈Create DM〉 |
| 開 DM 的限制 | 官方警告：不要用來對伺服器所有人群發 DM；「DMs should generally be initiated by a user action」；太快開太多 DM，bot 可能被 rate limit 或封鎖開新 DM。`40003` = "You are opening direct messages too fast" | 同上、Opcodes and Status Codes |
| 送訊息 | `POST /channels/{channel.id}/messages`，對 DM channel 同樣適用（"Post a message to a guild text or DM channel"）；`content` ≤ 2000、`embeds` ≤ 10 且總和 ≤ 6000 字元、`components`、`allowed_mentions`；標頭 `Authorization: Bot <token>` | Message Resource〈Create Message〉 |
| 私訊的前提 | 官方 API 文件沒有一句話列出前提。能查到的：錯誤碼 `50278` = "Cannot send messages to this user due to having no mutual guilds"（無共同伺服器）、`50007` = "Cannot send messages to this user"、`40002` = 需驗證帳號。Help Center 對一般使用者 DM 失敗列的原因：無共同伺服器、在共同伺服器關閉 DM、未完成 membership screening、對方只接受好友 DM、被封鎖 | Opcodes and Status Codes；Help Center「Why isn't my DM going through?」https://support.discord.com/hc/en-us/articles/360060145013-Why-isn-t-my-DM-going-through |
| `50007` 是否專指「使用者關閉允許伺服器成員私訊」 | 官方碼表只有 "Cannot send messages to this user"，沒有進一步說明對應哪個隱私設定（未查到）。實作上應把 `50007`、`50278` 都當作「無法私訊該使用者」處理，並提示使用者檢查共同伺服器與 DM 隱私設定。**2026-10-21 實測（M4 票 121）：收件人在唯一的共同伺服器關掉「私人訊息」時回的是 `50278`，不是 `50007`**，與沒有共同伺服器分不出（brief §20.23） | Opcodes and Status Codes |
| user-installed app 能否主動私訊 | 文件描述 user install：app 對授權者的 servers、DMs、GDMs 可見，且受使用者權限約束；**未查到**「user-installed app 能不經互動主動對使用者開 DM 並發訊息」的明文 | Application Resource〈User Context〉 |
| 權限與 intent | 發送 DM 不需 guild 權限（`SEND_MESSAGES` 只針對 guild channel）；送到 guild channel 時需要該頻道的 `SEND_MESSAGES`（以及 View Channel，後者此處未在 Create Message 條文中列出，未逐字查到）。送 REST 不需要任何 gateway intent；intent 只影響 gateway 收事件 | Message Resource〈Create Message〉〈Limitations〉、Gateway〈Intents〉 |

## 3. 收訊息與按鈕互動（為 M7）

| 事實 | 結論 | 來源 |
|---|---|---|
| 互動投遞方式 | 兩種且互斥："you can _only_ receive Interactions one of the two ways"：(a) gateway `INTERACTION_CREATE` 事件；(b) 對你設定的 Interactions Endpoint URL 發 HTTP outgoing webhook。預設是 gateway，要用 HTTP 需在 app 設定填 Endpoint URL | Receiving and Responding 開頭；Interactions Overview〈Preparing for Interactions〉 |
| 這兩條是唯一途徑嗎 | 文件只列這兩種，沒有第三種（結論來自文件的窮舉敘述） | 同上 |
| Endpoint URL 的要求 | "a public endpoint"；Discord 會先 POST 一個 `type: 1` 的 PING，要回 `200` + `{"type":1}`；每個請求都要驗 `X-Signature-Ed25519` 與 `X-Signature-Timestamp`（用 app 的 public key，Ed25519，簽的是 `timestamp + raw body`），驗證失敗回 `401`。文件稱 "public endpoint"，HTTPS 是否為硬性要求，在這幾頁中未逐字查到 | Interactions Overview〈Setting Up an Endpoint〉 |
| 無公開網址時 | 只剩 gateway websocket 能收互動：正確（因為 HTTP 路線需要 Discord 能連到的公開 endpoint） | 同上 |
| 回應時限 | 收到互動後 3 秒內必須給初始回應，否則 token 作廢；interaction token 有效 15 分鐘，可用來發 followup / 編輯原訊息 | Receiving and Responding |
| 按鈕按下 | 互動式 button（有 `custom_id`）會對 app 送 interaction；Link button 與 Premium button 不會 | Components Reference〈Button〉 |
| gateway 路線的 intent | `INTERACTION_CREATE` 不在任何 intent 的事件清單內；官方說明「Any events not listed means it's not associated with an intent and will always be sent」，所以接互動不需要 privileged intent | Gateway〈Intents〉 |
| 收 DM 訊息 | gateway 收 DM 的 `MESSAGE_CREATE` 需要 `DIRECT_MESSAGES (1 << 12)` intent（非 privileged）。`MESSAGE_CONTENT (1 << 15)` 是 privileged intent，但「沒有該 intent 的 app 仍可拿到的內容」包含：app 自己送的訊息、**與 app 的 DM 內容**、提到 app 的訊息、對其使用 message context menu command 的訊息。結論：收「使用者私訊 bot」的文字不需要 MESSAGE_CONTENT；在伺服器頻道中讀一般訊息才需要 | Gateway〈Intents〉〈Message Content Intent〉 |
| privileged intent 的門檻 | 少於 10,000 users 的 app 可直接在 Developer Portal 開啟 privileged intents，超過才需審查 | Gateway〈Privileged Intent Access Review〉 |
| 使用 gateway 的代價 | 長連線（Hello、heartbeat、Identify、resume、重連策略），要自行實作或引入程式庫；Berth 目前無 discord.py 依賴（此項是 Berth 側成本，非 Discord 文件內容） | Gateway |

## 4. 身分綁定

| 做法 | 是否需要 gateway | 事實 | 來源 |
|---|---|---|---|
| 使用者手動貼 user ID | 否 | 使用者在 User Settings > Advanced 開 Developer Mode，之後對自己的頭像 / 名稱右鍵 "Copy ID"（行動版同樣）。ID 為 17-18 位數字（Help Center「How to Find User IDs for Law Enforcement」https://support.discord.com/hc/en-us/articles/4407571667351 原文） | Help Center「Where can I find my User/Server/Message ID?」https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID |
| OAuth2 `identify` scope | 否（但需要 redirect URI） | `identify` 允許呼叫 `/users/@me`（不含 email）取得 user id。OAuth2 授權流程以 redirect URI 把結果帶回 app（見 OAuth2 文件的 URL 範例）。無公開網址時要靠使用者在本機瀏覽器開的 `localhost` 或內網位址作 redirect，**這是否被允許（redirect URI 需預先註冊，localhost 是否可）在此未查到** | OAuth2〈Shared Resources：OAuth2 Scopes〉 |
| slash command | 需要互動通道 | 使用者對 bot 打指令，interaction payload 帶 `user` / `member`，bot 即得到對方 ID。需要第 3 節的兩條路之一（無公開網址則為 gateway） | Receiving and Responding |
| 使用者先私訊 bot | 需 gateway | 收到 DM 的 `MESSAGE_CREATE` 帶 `author.id`；需 `DIRECT_MESSAGES` intent | Gateway〈Intents〉 |
| 不連 gateway、無公開網址 | - | 可行的只有「使用者手動貼 user ID」與（條件不明的）OAuth2 localhost redirect；其餘都需要 gateway。貼上後可用 `POST /users/@me/channels` 開 DM 並送一則測試訊息，由 `50007` / `50278` 回報驗證結果 | 綜合以上 |

## 5. 成熟產品怎麼做

- **Overseerr**：Discord agent 使用頻道 webhook（`axios.post(settings.options.webhookUrl, {...})`）。使用者可選填自己的 Discord user ID，開啟 `enableMentions` 後在 `content` 組 `<@id>`。文件原文："Users can optionally opt-in to being mentioned in Discord notifications by configuring their Discord user ID in their user settings"，webhook URL 取自 Server Settings > Integrations > Webhooks。來源：https://github.com/sct/overseerr/blob/develop/server/lib/notifications/agents/discord.ts 、https://github.com/sct/overseerr/blob/develop/docs/using-overseerr/notifications/discord.md
- **Jellyseerr**：沿用同一模型：webhook URL、`<@id>` mention，另外支援多個 `discordIds`、`<@&role>` role mention、`webhookThreadId`（`thread_id` query），並明確填 `allowed_mentions: { users, roles }` 限縮被 ping 的對象。來源：https://github.com/Fallenbagel/jellyseerr/blob/develop/server/lib/notifications/agents/discord.ts
- **Sonarr / Radarr**：Discord connection 只有 `WebHookUrl` 設定，`DiscordProxy` 直接 `POST` payload 到該 URL；Sonarr 的此檔未見 mention 或 bot token 邏輯。Radarr 未逐檔核對，視為同架構（推測，未查證）。來源：https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Notifications/Discord/DiscordProxy.cs 、`Discord.cs`（同目錄，設定連結指向 Discord 的 Intro to Webhooks）
- **Jellyfin**：官方 `jellyfin-plugin-webhook` 有 Discord destination（`Destinations/Discord/DiscordClient`），也有 generic 與 Slack destination；Discord 範本含 `content: "{{MentionType}}"`、`username`、`avatar_url`、`embeds`。同時有 issue 顯示 2026-02 Discord destination 在預設設定下回 `50109 The request body contains invalid JSON`，用 Generic 才正常（#369），提示不要假設某插件的 Discord 專用 destination 永遠可用。來源：https://github.com/jellyfin/jellyfin-plugin-webhook/issues/369 、https://github.com/jellyfin/jellyfin-plugin-webhook/issues/239

共同模式：四者都走「使用者貼頻道 webhook URL」，沒有任何一個要求使用者建立自己的 Discord bot；個人化 mention 靠使用者手動填 user ID。我只核對了上列檔案，不代表其他通知渠道或其他版本的行為。

## 6. 長度上限

| 項目 | 上限 | 來源 |
|---|---|---|
| `content` | 2000 字元 | Webhook Resource、Message Resource〈Create Message〉 |
| embeds 數量 | 每則訊息最多 10 個 | 同上 |
| embed `title` | 256 字元 | Message Resource〈Embed Limits〉 |
| embed `description` | 4096 字元 | 同上 |
| embed `fields` | 最多 25 個 | 同上 |
| `field.name` | 256 字元 | 同上 |
| `field.value` | 1024 字元 | 同上 |
| `footer.text` | 2048 字元 | 同上 |
| `author.name` | 256 字元 | 同上 |
| 單則訊息所有 embed 的 title + description + field.name + field.value + footer.text + author.name 合計 | 6000 字元，超過回 Bad Request | 同上 |
| 單次請求大小（Create Message） | 25 MiB | Message Resource〈Create Message〉〈Limitations〉 |
| button `label` | 80 字元；`custom_id` 1-100 字元；link `url` 最多 512 字元；一個 Action Row 最多 5 個 button 或 1 個 select | Components Reference |
| `IS_COMPONENTS_V2` 訊息 | 最多 40 個 components；該 flag 設了就不能再用 `content`、`embeds`、`poll`、`stickers`，且不可還原 | Components Reference、Using Message Components |

文件另註：Discord 可能剝掉內容中的某些字元（無效 unicode、會造成非預期格式的字元）；含使用者輸入的字串要消毒並設 `allowed_mentions`。

## 對 Berth 的意涵

不替使用者拍板，只列三種形狀在 M4（只送）與 M7（收訊息、按鈕）的可行性與代價。

### A. 頻道 webhook（可 @mention）

- **M4**：可行且最簡。使用者在頻道設定建 webhook，貼 URL 進 Berth；`POST` 帶 `content: "<@user_id>"` 加 `embeds`，`allowed_mentions: {"users": [...]}` 限縮。不需要 bot、不需要 gateway、不需要公開網址，單一 httpx POST。全部在 httpx 內即可，與 Overseerr / Jellyseerr / Sonarr 同一模型，使用者熟悉。
- **M4 限制**：必須有一個共享頻道（使用者要有伺服器，通常是自建的私人伺服器）；別人也看得到頻道內容；推播取決於使用者對該頻道的通知設定（文件不保證 mention 一定推播）；不能 DM。webhook URL 是 secret。需處理 429 的 `retry_after` 與 404（URL 已被刪）。
- **M7**：不可行。手動建的 webhook 不能送互動元件（只能送 Link 等非互動元件，Link 的適用性本身未查到明文），也沒有 application 可接收互動；不能收訊息。若 M7 要改用 A，最多是「訊息帶 Link button 連回 Berth UI」之類的導流（Berth UI 是否從手機可達，視使用者網路而定）。
- **代價**：M7 要另外加一條路，或 A 與 B/C 並存；webhook 設定在 M4 已有的資料格式不能直接升級成可互動。

### B. Bot 私訊（`POST /users/@me/channels` + `POST /channels/{id}/messages`）

- **M4**：技術上可行，純 REST、帶 `Authorization: Bot <token>`；不需要任何 intent。前提與風險：使用者必須與 bot 有共同伺服器（`50278`），並允許該來源 DM（`50007`），所以仍需要使用者建伺服器並邀請 bot；使用者需要自建 Discord application、取得 bot token、邀請 bot，設定步驟比 webhook 多；使用者還要提供自己的 user ID（可用 Developer Mode 複製）。「純 REST 不連過 gateway 是否能送」官方文件未查到明文要求；2026-10-21 實測可以（brief §20.23）。DM 的 mention 不是必須，直接收到私訊即推播（推播偏好取決於使用者）。
- **M7**：按鈕互動與收訊息都需要互動通道：無公開網址時只能 gateway（`INTERACTION_CREATE` 不需 intent；收 DM 訊息內容不需要 `MESSAGE_CONTENT`，需要 `DIRECT_MESSAGES` intent）。有公開 HTTPS 網址時可改走 Interactions Endpoint URL（需簽章驗證，3 秒內回應）。兩條路互斥。
- **代價**：M4 的資料格式要存 bot token + user ID；M7 要引入 gateway client（自寫或套件，Berth 目前沒有 discord.py 依賴）與常駐連線的生命週期管理；使用者要持有 bot。bot token 是高權限 secret。DM 有濫發保護（`40003`），Berth 的量級（個位數使用者）不太可能觸及。

### C. Bot 在頻道發訊息（`POST /channels/{id}/messages`，頻道內 `<@id>` mention）

- **M4**：可行，需要 bot token、bot 已加入該伺服器、頻道的 `SEND_MESSAGES`。可帶 mention（`allowed_mentions` 預設 parse 全部，應明確限縮）。比 A 多出 bot 設定，沒有 M4 層面的額外好處，除了 M7 可共用同一個 bot。
- **M7**：與 B 在互動通道上相同（無公開網址只能 gateway）。差別在 Proposal 訊息發在共享頻道，所有能看到頻道的人都看得到、也都能按；需要在互動 payload 的 `member.user.id` 驗證是否為授權使用者，並決定未授權者按下時的回應（ephemeral 回應是文件有的功能，flag `EPHEMERAL`）。在頻道讀一般訊息需要 `MESSAGE_CONTENT`（privileged，< 10,000 users 可在 Portal 直接開）。
- **代價**：同 B 的 bot 與 gateway 成本，加上頻道可見性的權限與隱私考量；好處是不依賴「共同伺服器 + 私訊隱私設定」這組會讓 B 失敗的條件（B 必定會遇到），但仍需要共同伺服器，因為 bot 必須在該伺服器內。

### 三者對照

| | A. 頻道 webhook | B. bot 私訊 | C. bot 頻道訊息 |
|---|---|---|---|
| 使用者設定 | 建 webhook、貼 URL（+ 選填 user ID） | 建 application / bot、邀請、貼 token + user ID | 同 B，另需指定頻道 |
| M4 需 gateway | 否 | 否（2026-10-21 實測） | 同 B |
| M4 需公開網址 | 否 | 否 | 否 |
| 手機推播 | mention 觸發，取決於使用者通知設定 | 私訊本身觸發，取決於使用者通知設定 | 同 A |
| 隱私 | 頻道成員可見 | 僅收件人 | 頻道成員可見 |
| M7 按鈕 | 不可（手動 webhook 不能送互動元件） | 可（gateway；有公開網址才可走 HTTP） | 同 B |
| M7 收訊息 | 不可 | 可（gateway；DM 內容不需 MESSAGE_CONTENT） | 可（gateway；頻道一般訊息需 MESSAGE_CONTENT） |
| 常見失敗 | 404（webhook 被刪）、429 | `50007`、`50278`、`40003`、429 | `50001`/`50013`（缺權限）、429 |
| 成熟產品先例 | Overseerr、Jellyseerr、Sonarr、Jellyfin webhook plugin | 本次核對的產品中未見 | 本次核對的產品中未見 |

### 需要實測才能定案的未查到項目

2026-10-21 更新（M4 票 121）：管道定為 bot 私訊、不做頻道 webhook（brief §19）之後，逐條的狀態如下。實測細節在 brief §20.23。

1. **已實測：可以。** 從沒連過 gateway 的 bot 開 DM channel 與送訊息都回 `200`（API v10）。
2. 未測，M4 用不到：通知走一般的 bot（guild install），不是 user-installed app。M7 若要讓使用者不必邀請 bot 進伺服器再回頭量。
3. 不再追：不做頻道 webhook（brief §19）。
4. 不再追：理由同上。bot 私訊的速率限制已實測（送訊息的 bucket 一次 5 則，開 DM channel 100）。
5. 未測，M7 的事：只有走 Interactions Endpoint URL 時才需要知道；沒有公開網址時 M7 走 gateway。
6. 未測，M4 用不到：身分綁定定為使用者手動填 user ID（plan §11.5）。

## 從 brief 搬來（§20.23）

**實測**（2026-10-21，M4 票 121，API v10，`scripts/experiments/discord_dm.py`；回應錄在 `tests/fixtures/http/discord/`）。兩個新建的 bot、一個只有使用者與 bot 的測試伺服器；第二個 bot 從頭到尾沒連過 gateway：

- **從沒連過 gateway 的 bot 私訊得到**：開 DM channel `200`、純文字與帶 embed 的訊息都 `200`，回完整的 message 物件。沒有任何 intent。
- **開 DM channel 什麼情況都回 `200`**（沒有共同伺服器、收件人關了私訊、bot 被踢出之後都是），擋下來的是送訊息那一步。所以「按測試」要真的送一則，只開 channel 證明不了什麼。
- **沒有共同伺服器與關了私訊回的是同一個錯**：`403`、`{"code": 50278, "message": "Cannot send messages to this user due to having no mutual guilds"}`。三種情況都量到這一個：bot 還沒被邀請、使用者在唯一的共同伺服器關掉「私人訊息」（已經聊過也一樣）、bot 被踢出伺服器。`50007` 一次都沒出現。Discord 算共同伺服器時只算開著私訊的那幾個，Berth 分不出是哪一種，提示要把兩個補法一起說：把 bot 加進同一個伺服器、在那個伺服器的隱私設定打開「私人訊息」。
- **伺服器的「私人訊息」預設可能是關的**：它跟著使用者的全域設定（使用者設定 → 私訊權限 →「加入伺服器後允許私訊」）。這次的測試帳號全域是關的，新建的伺服器也就是關的，第一次私訊就是 `50278`。打開後訊息直接進私訊清單；同時開著的「訊息請求」沒有把它攔下。
- **超過長度是 `400` / `50035` `Invalid Form Body`**，`errors` 指出欄位：`content` 2001 字元是 `errors.content._errors[].code = "BASE_TYPE_MAX_LENGTH"`（`Must be 2000 or fewer in length.`）；兩個 embed 的 description 合計 6001 字元是 `errors.embeds._errors[].code = "MAX_EMBED_SIZE_EXCEEDED"`（`Embed size exceeds maximum size of 6000`）。長度檢查在共同伺服器檢查之前：bot 被踢出之後送 2001 字元照樣先回 `400`，同一刻的純文字回 `403` / `50278`（`send too-long-no-mutual-guild --length 2001`）。
- **token 錯是 `401`**、`{"message": "401: Unauthorized", "code": 0}`，沒有 `X-RateLimit-*` header。
- **送訊息的 bucket 一次 5 則**（`X-RateLimit-Limit: 5`；兩個 bot、兩個 channel 的 `X-RateLimit-Bucket` 是同一個 hash，這次每個 bot 只量了一個 channel，分不出是按 channel 還是按 bot 算），失敗的請求（`400`、`403`）也扣額度；`X-RateLimit-Reset` 每送一則往後推約 1 秒，額度是一則一則補回來的，不是 5 秒整批重置。baseline 送完 4 則之後接著連續送、不間隔，第 7 則遇到 `429`。`429` 的 body 是 `{"message": "You are being rate limited.", "retry_after": 0.3, "global": false}`（**沒有 `code`**），header 有 `Retry-After: 5`（整數秒）、`X-RateLimit-Scope: user`、`X-RateLimit-Remaining: 0`、`X-RateLimit-Reset-After: 4.177`。body 的 `retry_after` 是下一個空位（浮點），header 的 `Retry-After` 是整個 bucket 重置、無條件進位成整數。開 DM channel 是另一個 bucket，`X-RateLimit-Limit: 100`。
- **只私訊的邀請連結**是 `https://discord.com/oauth2/authorize?client_id=<application id>&scope=bot&permissions=0`：`bot` scope 才會讓 bot 進伺服器（共同伺服器），私訊不需要任何伺服器權限。application id 由 `GET /applications/@me` 以 bot token 取得。新建的 application `bot_public` 預設 `true`、`bot_require_code_grant` 預設 `false`。
- **`GET /applications/@me` 回 Application Object**，Berth 只讀 `id` 與 `name`（官方文件 Application Resource〈Get Current Application〉與〈Application Object〉，https://discord.com/developers/docs/resources/application ，2026-10-21 經 context7 查 `discord/discord-api-docs`；M4 票 123）。這一份回應沒有錄：裡面有 application 擁有者的帳號（票 121 刻意不存），契約測試只用這兩格。錯的 token 在這一支同樣是 `401`。
- **embed 的 `url` 不收沒有點的主機名**（2026-10-21，M4 票 124，`discord_dm.py embed-url`；摘要在 `.local/experiments/results/discord_dm/embed-url-summary.json`，不進版控）：官方文件的 Embed Structure 只寫 `url?` string「url of embed」（經 context7 查 `discord/discord-api-docs`），沒寫檢查規則。對九種自架網址形狀（路徑 `/media/tv:120089`）各送一則：網域、子路徑、`*.ts.net`、`nas.local`、`192.168.1.10`、`127.0.0.1`、`localhost`、`[::1]` 都 `200`，回的 embed 原樣帶著 `url`；**`http://berth:8000/…` 是 `400` / `50035`、`errors.embeds.0.url._errors[].code = "URL_TYPE_INVALID_URL"`（`Not a well formed URL.`）**，整則送不出。同一個網址寫成 description 裡的 Markdown 連結（`[打開](http://berth:8000/…)`）九種都 `200`，所以 Berth 的連結放在 description（`adapters/notify/discord._description`）。手機上 Markdown 連結是否每一種都可點沒有逐一看。

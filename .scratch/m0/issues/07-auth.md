# 07 — 認證：Jellyfin 登入與 session

**Status:** done

**Blocked by:** 06

**讀:** plan §6（auth 群組）、§8.2、§11.1（T0.5）；brief §11、§16.2

## 做什麼

登入頁 + 以 Jellyfin 帳密登入換 Berth session。角色由 Jellyfin 的 `Policy.IsAdministrator` 決定，非 admin 使用者進不了設定。session 以 httpOnly cookie 承載，非 GET 請求要求 `X-Requested-With` 標頭作 CSRF 防線。

## 驗收

- [x] `POST /api/auth/login` 以 `Users/AuthenticateByName` 驗證，成功後建立 `users` 與 `sessions` 列，回 httpOnly、`SameSite=Strict` cookie
- [x] `GET /api/auth/me` 回使用者與角色；`POST /api/auth/logout` 使 session 失效
- [x] 非 GET 請求缺 `X-Requested-With` 標頭時回 403
- [x] 未登入呼叫任何非白名單 API 回 401，前端導向 `/login`
- [x] `Policy.IsAdministrator=false` 的使用者登入後看不到設定入口，直接打設定 API 也回 403
- [x] session 過期後自動失效，過期 session 不能續用
- [x] 密碼不寫進 log，錯誤訊息不區分「帳號不存在」與「密碼錯誤」
- [x] 登入頁走 impeccable `shape`
- [x] playwright 跑通登入、登出、非 admin 權限阻擋三條路徑並附結果

## Comments

### playwright 實跑結果（`--scenario signed-out`，深淺兩主題）

| 路徑 | 結果 |
| --- | --- |
| 匿名開 `/` | 導向 `/login?redirect=%2F`，只剩一個 401（`auth/me`）在 console |
| 管理員登入 | `skipper` / `harbour` → 落到 `/`，頁首 `管理員 · skipper · 設定 · 登出` |
| 已登入再開 `/login?redirect=%2Fsetup` | 直接送到 `/setup`，不再看一次表單 |
| 登出 | 回 `/login`，且**不**顯示「已過期」（那是自己按的） |
| 非 admin 登入 | `deckhand` / `rope` → 頁首只有 `使用者 · deckhand · 登出`，沒有設定入口 |
| 非 admin 打設定 API | `GET /api/setup/status` 403、`GET /api/setup/not-built-yet` 403、`POST /api/setup/detect` 403 |
| 缺 CSRF 標頭 | `POST /api/auth/logout` 403 |
| `document.cookie` | 空字串——session cookie 是 httpOnly，JS 讀不到 |
| 少一個欄位的登入 | 401（不是 422），回應不含送出去的密碼 |
| 型別錯誤的登入 | 422，回應不含送出去的值，只留 `loc` 與 `msg` |

對比實測（canvas 取樣算 WCAG 對比）：亮色最低 **5.71:1**（`.label` 的 `ink-dim` on `well`），
深色最低 **6.53:1**。窄版 390×780 兩頁都不破版。

### code-review 的發現與處置

全部已修，沒有留待辦：

- **`ensureQueryData` 不會重抓**（Spec 軸）——門禁拿快取放行，session 在使用中失效之後前端
  永遠導不到 `/login`，`expired` 那條路也走不到。改用 `fetchQuery`，並加了一條先紅後綠的
  回歸測試（`router.test.tsx`「session 在使用中失效之後…」）。
- **422 會把密碼原樣回傳**（自己在收尾時發現）——`POST /auth/login` 少一個欄位時，
  pydantic 把整份 body 放進 `input`。新增 `api/errors.py` 把 `input` / `ctx` 從 422 回應剝掉，
  並讓 `LoginIn` 的欄位有預設值（缺欄位走 401，不給人 422/401 的差別當試探）。
- **`/setup` 在門禁上是 default-allow 的洞**（Standards 軸）——規則原本一半在門禁的白名單、
  一半在 router 的相依，之後新掛在 `/api/setup` 底下的 router 會預設匿名。整條規則搬進門禁，
  `require_setup_open` 刪除，並加測試釘住「沒有 router 認領的 setup 路徑一樣被擋」。
- **`BaseHTTPMiddleware` 會把回應收進記憶體**（Standards 軸）——plan §6 的 `GET /events/stream`
  在它底下就不是串流。門禁改寫成純 ASGI middleware。
- **登入頁把所有錯誤都說成「帳號或密碼不對」**（Standards 軸）——403 / 500 / 斷線都會讓使用者
  一直重打其實正確的密碼。加第三個分支（帶 HTTP 狀態碼與 `docker compose logs` 的下一步）。
- **`destination()` 沒擋 `/\`**（Standards 軸）——瀏覽器把它當通訊協定相對網址。已擋，
  並搬到 `web/src/auth/destination.ts`（在 `LoginPage.tsx` 匯出非元件會壞掉 fast refresh）。
- **被拒絕之後焦點沒回到密碼欄**（Spec 軸，shape brief §5）——已補，附測試。
- **已登入的人開 `/login` 仍看得到表單**（Spec 軸，shape brief §5）——已補，附測試。
- **`is_admin` / `jellyfin_user_id` / `SignedIn.expires_at` 沒有消費者**（Standards 軸）——已刪。
- **CHANGELOG 沒更新**（Standards 軸）——已補。

未處理（有意）：

- 帳號長度沒有上限（shape brief §5 寫 1–255）。Jellyfin 自己會拒，Berth 多一層長度檢查只會
  在兩邊不一致時變成假的錯誤訊息。
- `routes.tsx` 的 `isSetupComplete` → `requireSession` 在兩個路由重複兩行。兩個分支的後續
  不同（一個 return、一個 redirect），現在抽共用比重複更難讀；頁面變多時再收。

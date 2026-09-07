# 07 — 認證：Jellyfin 登入與 session

**Status:** ready-for-agent

**Blocked by:** 06

**讀:** plan §6（auth 群組）、§8.2、§11.1（T0.5）；brief §11、§16.2

## 做什麼

登入頁 + 以 Jellyfin 帳密登入換 Berth session。角色由 Jellyfin 的 `Policy.IsAdministrator` 決定，非 admin 使用者進不了設定。session 以 httpOnly cookie 承載，非 GET 請求要求 `X-Requested-With` 標頭作 CSRF 防線。

## 驗收

- [ ] `POST /api/auth/login` 以 `Users/AuthenticateByName` 驗證，成功後建立 `users` 與 `sessions` 列，回 httpOnly、`SameSite=Strict` cookie
- [ ] `GET /api/auth/me` 回使用者與角色；`POST /api/auth/logout` 使 session 失效
- [ ] 非 GET 請求缺 `X-Requested-With` 標頭時回 403
- [ ] 未登入呼叫任何非白名單 API 回 401，前端導向 `/login`
- [ ] `Policy.IsAdministrator=false` 的使用者登入後看不到設定入口，直接打設定 API 也回 403
- [ ] session 過期後自動失效，過期 session 不能續用
- [ ] 密碼不寫進 log，錯誤訊息不區分「帳號不存在」與「密碼錯誤」
- [ ] 登入頁走 impeccable `shape`
- [ ] playwright 跑通登入、登出、非 admin 權限阻擋三條路徑並附結果

## Comments

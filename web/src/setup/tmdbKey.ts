/**
 * 貼上的字串像不像 TMDB 的憑證（M4 票 31）。
 *
 * TMDB 的帳號頁發兩種：v3 的 API key 是 32 個十六進位字元，v4 的 read access token 是 JWT（兩個點分成
 * 三段）。後端認的也是這兩種形狀（`adapters/tmdb.credential_auth`）。兩種都不像時不送：測不過的 key
 * 照樣存下（使用者才能改一個字再按一次），而明顯不是 key 的字串存下來只會讓畫面說「已存下，沒通過驗證」。
 */
const API_KEY = /^[0-9a-f]{32}$/i
const ACCESS_TOKEN = /^[\w-]+\.[\w-]+\.[\w-]+$/

export function looksLikeTmdbKey(value: string): boolean {
  const trimmed = value.trim()
  return API_KEY.test(trimmed) || ACCESS_TOKEN.test(trimmed)
}

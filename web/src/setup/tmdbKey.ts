/**
 * 貼上的字串像不像 TMDB 的憑證（M4 票 31）。
 *
 * TMDB 的帳號頁發兩種：v3 的 API key 是 32 個十六進位字元，v4 的 read access token 是 JWT（兩個點分成
 * 三段）。後端認的也是這兩種形狀（`adapters/tmdb.credential_auth`）。兩種都不像時不送：明顯不是 key 的
 * 字串不必打去 TMDB 才知道不行，欄位當場說得出是哪裡不對。
 */
const API_KEY = /^[0-9a-f]{32}$/i
const ACCESS_TOKEN = /^[\w-]+\.[\w-]+\.[\w-]+$/

export function looksLikeTmdbKey(value: string): boolean {
  const trimmed = value.trim()
  return API_KEY.test(trimmed) || ACCESS_TOKEN.test(trimmed)
}

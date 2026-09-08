const PROTOCOL_RELATIVE = ['//', '/\\']

/**
 * 登入後要去哪裡。`?redirect=` 來自網址列，所以只收站內路徑——少了這道檢查，一條
 * `?redirect=https://…` 的連結就能把剛登入的人送到別人的網站去。開頭是 `//` 或 `/\`
 * 的字串瀏覽器都當成通訊協定相對網址，兩種都要擋。
 *
 * **清洗做在這裡而不是路由的 `validateSearch`**：TanStack Router 會把父路由沒宣告的
 * search 參數原樣往下傳，子路由的驗證結果只是疊在上面，刪不掉它（實測 1.171）。
 */
export function destination(redirect: string | undefined): string {
  if (redirect === undefined || !redirect.startsWith('/')) return '/'
  return PROTOCOL_RELATIVE.some((prefix) => redirect.startsWith(prefix)) ? '/' : redirect
}

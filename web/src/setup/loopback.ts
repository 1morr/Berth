/**
 * 使用者填的既有服務位址是不是指到 Berth 自己（brief §16.4、§20.14，M4 票 17）。
 *
 * Berth 在容器裡：`localhost`、`127.0.0.0/8`、`::1` 是 Berth 這個容器，不是宿主。測試只會說「連不上」，
 * 所以位址欄下就地提示改成 `host.docker.internal` 或區網 IP，測試不過時的補法也帶同一句。**只提示、不擋**：
 * `network_mode: host` 之類的部署填 `localhost` 是對的。
 *
 * 使用者常省略 scheme（`localhost:8080`），所以先補一個再交給 `URL` 解析；解析不了的一律不提示。
 */
export function pointsAtBerth(address: string): boolean {
  const trimmed = address.trim()
  if (!trimmed) return false
  const host = hostOf(trimmed)
  if (host === null) return false
  return host === 'localhost' || host === '[::1]' || /^127(\.\d{1,3}){3}$/.test(host)
}

function hostOf(address: string): string | null {
  // 裸的 `::1` 不是合法的 URL 主機，照使用者的意思當成 `[::1]`。
  const bracketed = address === '::1' ? '[::1]' : address
  const withScheme = /^[a-z][a-z\d+.-]*:\/\//i.test(bracketed) ? bracketed : `http://${bracketed}`
  try {
    return new URL(withScheme).hostname.toLowerCase()
  } catch {
    return null
  }
}

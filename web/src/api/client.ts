// 後端與前端由同一個程序提供，所以一律走相對路徑；開發時 Vite 代理 /api（vite.config.ts）。
const API_PREFIX = '/api'

/**
 * 回傳值目前是手寫型別。API 面長出來之後改用 openapi-typescript 從 OpenAPI 產（plan §6）。
 */
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`)
  }

  return (await response.json()) as T
}

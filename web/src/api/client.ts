// 後端與前端由同一個程序提供，所以一律走相對路徑；開發時 Vite 代理 /api（vite.config.ts）。
const API_PREFIX = '/api'

/** 後端回的錯誤。`status` 讓呼叫端分得出「還沒設定好」與「真的壞了」。 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * 回傳值目前是手寫型別。API 面長出來之後改用 openapi-typescript 從 OpenAPI 產（plan §6）。
 */
export async function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    method,
    headers: {
      Accept: 'application/json',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      // 非 GET 一律帶這個標頭作 CSRF 防線（plan §6）；後端的檢查在票 07。
      ...(method === 'GET' ? {} : { 'X-Requested-With': 'XMLHttpRequest' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    throw new ApiError(response.status, `${method} ${path} failed with ${response.status}`)
  }

  // 204 沒有 body（登出就是），硬 parse 會炸在 JSON.parse 上而不是回傳 void。
  if (response.status === 204) return undefined as T

  return (await response.json()) as T
}

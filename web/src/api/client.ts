// 後端與前端由同一個程序提供，所以一律走相對路徑；開發時 Vite 代理 /api（vite.config.ts）。
const API_PREFIX = '/api'

/**
 * 後端回的錯誤。`status` 讓呼叫端分得出「還沒設定好」與「真的壞了」。
 *
 * `detail` 是後端 `HTTPException` 的那一格，原樣帶著（可能是一句話、一串驗證錯誤，
 * 或票 09 送單那種 `{reason, detail}`）。**帶著它而不是只留一個狀態碼**：拒絕的理由
 * 是封閉集合，而畫面要照理由說出下一步（PRODUCT 原則 4）——只有狀態碼的話
 * 「這條 Route 是紅的」與「這條 Route 停用了」在畫面上是同一句話。
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown = undefined) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/**
 * `T` 一律是 `pnpm gen:api` 從 OpenAPI 產出的型別（plan §6）；`api/*.ts` 那一層只是
 * 把後端的類別名換成前端在講的名字，沒有一個形狀是手寫的。
 *
 * 這裡不做 path → 型別的推導：回應型別由呼叫端指定 `T`，請求的 body 則在呼叫端以
 * `satisfies Schemas['...']` 檢查（`body` 在這一層是 `unknown`）。
 */
export async function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body)
}

/**
 * 多數成功是 204，沒有 body（`request` 對 204 回 `undefined`）；標為未看回寫入之後的狀態，
 * 所以回應型別由呼叫端指定。
 */
export async function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', path)
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
    throw new ApiError(
      response.status,
      `${method} ${path} failed with ${response.status}`,
      await detailOf(response),
    )
  }

  // 204 沒有 body（登出就是），硬 parse 會炸在 JSON.parse 上而不是回傳 void。
  if (response.status === 204) return undefined as T

  return (await response.json()) as T
}

/** 錯誤回應的 `detail`。不是 JSON（前置代理回一頁 HTML）時就是 `undefined`。 */
async function detailOf(response: Response): Promise<unknown> {
  try {
    return ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return undefined
  }
}

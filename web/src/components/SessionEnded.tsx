import { useEffect, type ReactNode } from 'react'
import { useRouter } from '@tanstack/react-router'

/**
 * 後端結束了這個 session（帳號在 Jellyfin 被停用，401 `account_disabled`）。重跑路由守衛：它問
 * `GET /auth/me` 拿到 401，就把人送到 `/login` 並說「登入已失效」——與 session 自然過期同一條路，不另寫一份。
 * 媒體庫頁與首頁上方的兩列共用（M1.5 票 03、07）。
 */
export function SessionEnded({ pending }: { pending: ReactNode }) {
  const router = useRouter()
  useEffect(() => {
    void router.invalidate()
  }, [router])
  // 守衛把人送走之前那一瞬間畫的東西。
  return pending
}

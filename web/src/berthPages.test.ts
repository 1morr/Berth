import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  type AnyRouter,
  type RegisteredRouter,
} from '@tanstack/react-router'
import { describe, expect, it } from 'vitest'

import type { components } from './api/schema'
import { createAppRouter, createQueryClient } from './router'

/**
 * 後端組的 Berth 網址開得到前端的那一頁（M5 票 02）。
 *
 * 通知裡的連結由後端照 `deeplink.BerthPage` 組（`/media/{media_id}`），路由在這邊
 * （`/media/$mediaId`）。那個封閉集合經 OpenAPI 進 `schema.d.ts`，所以：
 *
 * - **後端加一頁或改模板**：`PAGES` 少一個鍵或多一個鍵，`tsc` 紅（`pytest` 先守產出沒過期）。
 * - **前端改路由**：模板解析不到原本那一條，這裡紅；`PAGES` 的值不是路由表上的路徑時 `tsc` 也紅。
 *
 * 值是那一條後端模板該落在哪一條路由上——寫明而不是「解析得到就好」，之後加了接住一切的 404 路由
 * 也不會讓每一條都算過。
 */
type BerthPage = components['schemas']['BerthPage']
type RoutePath = keyof RegisteredRouter['routesByPath']

const PAGES: Record<BerthPage, RoutePath> = {
  '/media/{media_id}': '/media/$mediaId',
  '/review': '/review',
  '/issues': '/issues',
  '/rss': '/rss',
  '/weekly/{report_id}': '/weekly/$reportId',
}

/** 這一條模板在 `router` 上落在哪一條路由。每一個 `{name}` 換成帶冒號的值，與作品 id（`tv:120089`）同形。 */
function landing(router: AnyRouter, template: string): string | undefined {
  const url = template.replace(/\{(\w+)\}/g, (_, name: string) => `sample:${name}`)
  const [, , found] = router.getMatchedRoutes(url)
  return found?.fullPath
}

describe('後端組的 Berth 網址', () => {
  const router = createAppRouter(createQueryClient(), createMemoryHistory())

  it.each(Object.entries(PAGES))('%s 落在 %s', (template, route) => {
    expect(landing(router, template)).toBe(route)
  })
})

describe('閘門本身（雙向）', () => {
  /** 一張只有作品頁與另一頁的路由表；`media` 與 `other` 是兩條的路徑。 */
  function routerWith(media: string, other: string) {
    const root = createRootRoute()
    const routeTree = root.addChildren([
      createRoute({ getParentRoute: () => root, path: media }),
      createRoute({ getParentRoute: () => root, path: other }),
    ])
    return createRouter({ routeTree, history: createMemoryHistory() })
  }

  it('前端把作品頁改名就紅', () => {
    expect(landing(routerWith('/title/$mediaId', '/library'), '/media/{media_id}')).not.toBe(
      '/media/$mediaId',
    )
  })

  it('改無關的路由不紅', () => {
    expect(landing(routerWith('/media/$mediaId', '/inventory'), '/media/{media_id}')).toBe(
      '/media/$mediaId',
    )
  })
})

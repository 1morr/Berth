import { describe, expect, it } from 'vitest'

import {
  commonRoot,
  hostSource,
  mountSnippet,
  remedyFor,
  runMount,
  type Remedy,
} from './routeChecks'

/** 要改的那一台：使用者自己的是 `mount`，其餘是片段的第一行（`  jellyfin:`）。 */
function serviceOf(remedy: Remedy): string | null {
  return (
    remedy.mount?.service ?? remedy.commands[0]?.split('\n')[0].trim().replace(/:$/, '') ?? null
  )
}

/** compose 傳進來的 `DATA_ROOT`（M4 票 63）。 */
const HOST = { path: '/srv/berth/data', relative: false }
const EXISTING_JELLYFIN = { jellyfin: true, qbittorrent: false, root: '/data', host: HOST }
const EXISTING_QBITTORRENT = { jellyfin: false, qbittorrent: true, root: '/data', host: HOST }

describe('remedyFor（M4 票 19：補法指對容器）', () => {
  it('library_path 紅而 Jellyfin 是既有：片段是 Jellyfin 的，說明是既有那一台的版本', () => {
    const remedy = remedyFor('library_path', { existing: EXISTING_JELLYFIN, crossDevice: false })

    expect(serviceOf(remedy)).toBe('jellyfin')
    expect(remedy.fix).toBe('routes.fix.existing.libraryMount')
  })

  it('probe_visible 紅：片段是 Jellyfin 的，不是 berth（Berth 早就有 /data）', () => {
    expect(
      serviceOf(remedyFor('probe_visible', { existing: EXISTING_JELLYFIN, crossDevice: false })),
    ).toBe('jellyfin')
    expect(serviceOf(remedyFor('probe_visible', { crossDevice: false }))).toBe('jellyfin')
  })

  it('探針（download_visible）紅：片段是 qBittorrent 的，既有與套件內說法分開', () => {
    const existing = remedyFor('download_visible', {
      existing: EXISTING_QBITTORRENT,
      crossDevice: false,
    })
    const bundled = remedyFor('download_visible', { crossDevice: false })

    expect(serviceOf(existing)).toBe('qbittorrent')
    expect(serviceOf(bundled)).toBe('qbittorrent')
    expect(existing.fix).toBe('routes.fix.existing.qbittorrentMount')
    expect(bundled.fix).toBe('routes.fix.qbittorrentMount')
  })

  it('EXDEV：片段是 berth 自己的；不是 EXDEV 的硬鏈接失敗不給片段', () => {
    expect(serviceOf(remedyFor('hardlink', { crossDevice: true }))).toBe('berth')
    expect(remedyFor('hardlink', { crossDevice: false }).commands).toEqual([])
  })

  it('Berth 看不到 qBittorrent 報的路徑（download_path）才是 berth', () => {
    expect(serviceOf(remedyFor('download_path', { crossDevice: false }))).toBe('berth')
  })

  it('片段的容器路徑跟著 Berth 自己的根目錄，不是寫死 /data', () => {
    const remedy = remedyFor('library_path', {
      existing: { ...EXISTING_JELLYFIN, root: '/volume1/media' },
      crossDevice: false,
    })

    expect(remedy.mount).toEqual({ service: 'jellyfin', root: '/volume1/media', host: HOST })
    expect(remedy.root).toBe('/volume1/media')
  })

  it('Berth 的下載與媒體庫沒有共同父目錄時不給片段（照貼會掛到容器的根）', () => {
    const remedy = remedyFor('library_path', {
      existing: { ...EXISTING_JELLYFIN, root: '/' },
      crossDevice: false,
    })

    expect(remedy.commands).toEqual([])
    expect(remedy.mount).toBeNull()
  })

  it('套件內（健康頁、設定頁讀不到來源）用 deploy/ 那一份的 /data', () => {
    const remedy = remedyFor('library_path', { crossDevice: false })

    expect(remedy.fix).toBe('routes.fix.libraryMount')
    expect(remedy.commands).toEqual(['  jellyfin:\n    volumes:\n      - ${DATA_ROOT}:/data'])
    expect(remedy.mount).toBeNull()
  })
})

describe('remedyFor（M4 票 25：補法照原因，不照檢查項目）', () => {
  // 檢查 1（建分類目錄）、3（寫探測檔給 qBittorrent）、5（寫探測檔給 Jellyfin）都會撞上 Berth 自己寫不進。
  const WRITING_CHECKS = ['category', 'download_visible', 'probe_visible'] as const

  it.each(WRITING_CHECKS)(
    'Berth 自己寫不進（%s）：同一條權限的補法、沒有任何片段，既有或套件內都一樣',
    (check) => {
      for (const existing of [undefined, EXISTING_JELLYFIN, EXISTING_QBITTORRENT]) {
        const remedy = remedyFor(check, {
          existing,
          crossDevice: false,
          failure: 'berth_cannot_write',
        })

        expect(remedy.fix).toBe('routes.fix.berthCannotWrite')
        expect(remedy.commands).toEqual([])
        expect(remedy.mount).toBeNull()
        expect(remedy.advice).toBeNull()
      }
    },
  )

  it('另一面：真正是別的容器看不到時，片段仍是那一台的', () => {
    expect(
      serviceOf(remedyFor('download_visible', { crossDevice: false, failure: 'probe_unseen' })),
    ).toBe('qbittorrent')
    expect(
      serviceOf(
        remedyFor('probe_visible', {
          existing: EXISTING_JELLYFIN,
          crossDevice: false,
          failure: 'jellyfin_cannot_see',
        }),
      ),
    ).toBe('jellyfin')
  })

  it('目錄被刪與不在共用掛載底下分開：前者不給片段，後者照舊是 Jellyfin 的片段', () => {
    const deleted = remedyFor('library_path', {
      existing: EXISTING_JELLYFIN,
      crossDevice: false,
      failure: 'directory_missing',
    })
    const outside = remedyFor('library_path', {
      existing: EXISTING_JELLYFIN,
      crossDevice: false,
      failure: 'path_not_visible',
    })

    expect(deleted.fix).toBe('routes.fix.directoryMissing')
    expect(deleted.commands).toEqual([])
    expect(deleted.mount).toBeNull()
    expect(outside.fix).toBe('routes.fix.existing.libraryMount')
    expect(serviceOf(outside)).toBe('jellyfin')
  })

  it.each([
    ['scheme_mismatch', 'connection.fix.schemeMismatch'],
    ['scheme_missing', 'connection.fix.schemeMissing'],
  ] as const)('位址的協定寫錯（%s）：說改位址，不說確認在跑、不給片段', (failure, fix) => {
    const remedy = remedyFor('category', { crossDevice: false, failure })

    expect(remedy.fix).toBe(fix)
    expect(remedy.commands).toEqual([])
  })
})

describe('commonRoot', () => {
  it.each([
    ['/data/torrent/complete', '/data/library', '/data'],
    ['/volume1/media/complete', '/volume1/media/library', '/volume1/media'],
    ['/data', '/data/library', '/data'],
    ['/downloads', '/movies', '/'],
  ])('%s + %s → %s', (a, b, root) => {
    expect(commonRoot(a, b)).toBe(root)
  })
})

describe('remedyFor（M4 票 36：既有服務只多掛一條 /data）', () => {
  const COMPOSE = (service: string) => `  ${service}:\n    volumes:\n      - \${DATA_ROOT}:/data`

  it.each([
    ['download_visible', EXISTING_QBITTORRENT, 'qbittorrent'],
    ['library_path', EXISTING_JELLYFIN, 'jellyfin'],
    ['probe_visible', EXISTING_JELLYFIN, 'jellyfin'],
  ] as const)(
    '%s 紅在你那一台：多加的是那一台的 /data，不給套件內的片段',
    (check, existing, service) => {
      const remedy = remedyFor(check, { existing, crossDevice: false })

      expect(remedy.mount).toEqual({ service, root: '/data', host: HOST })
      expect(remedy.commands).toEqual([])
    },
  )

  it('套件內那一台與 berth 自己的掛載是這套 compose 的片段：與 deploy/ 一字不差', () => {
    expect(remedyFor('download_visible', { crossDevice: false }).commands).toEqual([
      COMPOSE('qbittorrent'),
    ])
    expect(
      remedyFor('hardlink', { existing: EXISTING_JELLYFIN, crossDevice: true }).commands,
    ).toEqual([COMPOSE('berth')])
    expect(
      remedyFor('download_path', { existing: EXISTING_QBITTORRENT, crossDevice: false }).commands,
    ).toEqual([COMPOSE('berth')])
  })
})

describe('既有服務的掛載帶 Berth 的 DATA_ROOT 真正的值（M4 票 63，審計 P1-6）', () => {
  const UNKNOWN = { path: '', relative: false }

  it('compose 與 docker run 都是那個資料夾，不再是 ${DATA_ROOT}', () => {
    const source = hostSource(HOST)

    expect(mountSnippet('jellyfin', '/data', source)).toBe(
      '  jellyfin:\n    volumes:\n      - /srv/berth/data:/data',
    )
    expect(runMount('/data', source)).toBe('-v /srv/berth/data:/data')
  })

  it('Windows 的值照後端換好的寫（C:/…），貼進 YAML 不必跳脫', () => {
    const source = hostSource({ path: 'C:/Berth/data', relative: false })

    expect(mountSnippet('qbittorrent', '/data', source)).toContain('      - C:/Berth/data:/data')
    expect(runMount('/data', source)).toBe('-v C:/Berth/data:/data')
  })

  it('不知道值（compose 沒傳進來）時照舊是 ${DATA_ROOT}', () => {
    expect(hostSource(UNKNOWN)).toBe('${DATA_ROOT}')
    expect(runMount('/data', hostSource(UNKNOWN))).toBe('-v ${DATA_ROOT}:/data')
  })

  it('路徑有空白時 docker run 那一段加引號；沒有就不加', () => {
    expect(runMount('/data', '/mnt/user/My Media')).toBe('-v "/mnt/user/My Media:/data"')
    expect(runMount('/data', '/mnt/user/media')).toBe('-v /mnt/user/media:/data')
  })
})

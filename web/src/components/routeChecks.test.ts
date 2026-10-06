import { describe, expect, it } from 'vitest'

import { commonRoot, remedyFor } from './routeChecks'

/** 片段第一行是要改的那一台：`  jellyfin:`。 */
function serviceOf(commands: readonly string[]): string | null {
  return commands[0]?.split('\n')[0].trim().replace(/:$/, '') ?? null
}

const EXISTING_JELLYFIN = { jellyfin: true, qbittorrent: false, root: '/data' }
const EXISTING_QBITTORRENT = { jellyfin: false, qbittorrent: true, root: '/data' }

describe('remedyFor（M4 票 19：補法指對容器）', () => {
  it('library_path 紅而 Jellyfin 是既有：片段是 Jellyfin 的，說明是既有那一台的版本', () => {
    const remedy = remedyFor('library_path', { existing: EXISTING_JELLYFIN, crossDevice: false })

    expect(serviceOf(remedy.commands)).toBe('jellyfin')
    expect(remedy.fix).toBe('routes.fix.existing.libraryMount')
  })

  it('probe_visible 紅：片段是 Jellyfin 的，不是 berth（Berth 早就有 /data）', () => {
    expect(
      serviceOf(
        remedyFor('probe_visible', { existing: EXISTING_JELLYFIN, crossDevice: false }).commands,
      ),
    ).toBe('jellyfin')
    expect(serviceOf(remedyFor('probe_visible', { crossDevice: false }).commands)).toBe('jellyfin')
  })

  it('探針（download_visible）紅：片段是 qBittorrent 的，既有與套件內說法分開', () => {
    const existing = remedyFor('download_visible', {
      existing: EXISTING_QBITTORRENT,
      crossDevice: false,
    })
    const bundled = remedyFor('download_visible', { crossDevice: false })

    expect(serviceOf(existing.commands)).toBe('qbittorrent')
    expect(serviceOf(bundled.commands)).toBe('qbittorrent')
    expect(existing.fix).toBe('routes.fix.existing.qbittorrentMount')
    expect(bundled.fix).toBe('routes.fix.qbittorrentMount')
  })

  it('EXDEV：片段是 berth 自己的；不是 EXDEV 的硬鏈接失敗不給片段', () => {
    expect(serviceOf(remedyFor('hardlink', { crossDevice: true }).commands)).toBe('berth')
    expect(remedyFor('hardlink', { crossDevice: false }).commands).toEqual([])
  })

  it('Berth 看不到 qBittorrent 報的路徑（download_path）才是 berth', () => {
    expect(serviceOf(remedyFor('download_path', { crossDevice: false }).commands)).toBe('berth')
  })

  it('片段的容器路徑跟著 Berth 自己的根目錄，不是寫死 /data', () => {
    const remedy = remedyFor('library_path', {
      existing: { ...EXISTING_JELLYFIN, root: '/volume1/media' },
      crossDevice: false,
    })

    expect(remedy.commands[0]).toContain('${DATA_ROOT}:/volume1/media')
    expect(remedy.root).toBe('/volume1/media')
  })

  it('Berth 的下載與媒體庫沒有共同父目錄時不給片段（照貼會掛到容器的根）', () => {
    const remedy = remedyFor('library_path', {
      existing: { ...EXISTING_JELLYFIN, root: '/' },
      crossDevice: false,
    })

    expect(remedy.commands).toEqual([])
  })

  it('套件內（健康頁、設定頁讀不到來源）用 deploy/ 那一份的 /data', () => {
    const remedy = remedyFor('library_path', { crossDevice: false })

    expect(remedy.fix).toBe('routes.fix.libraryMount')
    expect(remedy.commands).toEqual(['  jellyfin:\n    volumes:\n      - ${DATA_ROOT}:/data'])
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
        expect(remedy.advice).toBeNull()
      }
    },
  )

  it('另一面：真正是別的容器看不到時，片段仍是那一台的', () => {
    expect(
      serviceOf(
        remedyFor('download_visible', { crossDevice: false, failure: 'probe_unseen' }).commands,
      ),
    ).toBe('qbittorrent')
    expect(
      serviceOf(
        remedyFor('probe_visible', {
          existing: EXISTING_JELLYFIN,
          crossDevice: false,
          failure: 'jellyfin_cannot_see',
        }).commands,
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
    expect(outside.fix).toBe('routes.fix.existing.libraryMount')
    expect(serviceOf(outside.commands)).toBe('jellyfin')
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

import { describe, expect, it } from 'vitest'

import { jellyfinBase, jellyfinDetailsUrl, jellyfinLibrariesUrl } from './jellyfinLink'

/** 瀏覽器現在在哪裡：Berth 開在 NAS 的 8383 上。 */
const HERE = { protocol: 'http:', hostname: 'nas.local' }

describe('jellyfinDetailsUrl', () => {
  it('後端給了位址就照用（對外網址或既有的 Jellyfin）', () => {
    expect(
      jellyfinDetailsUrl(
        { public_url: '', url: 'https://jf.example.com', port: null },
        'b268',
        HERE,
      ),
    ).toBe('https://jf.example.com/web/#/details?id=b268')
  })

  it('套件內的 Jellyfin 開在瀏覽器自己的主機名上——compose 內網的名字瀏覽器解不到', () => {
    expect(jellyfinDetailsUrl({ public_url: '', url: '', port: 8096 }, 'b268', HERE)).toBe(
      'http://nas.local:8096/web/#/details?id=b268',
    )
  })

  it('還沒找到 item 時沒有連結，不給一條點了會 404 的死連結', () => {
    expect(jellyfinDetailsUrl({ public_url: '', url: '', port: 8096 }, '', HERE)).toBeNull()
  })

  it('既不知道位址也不知道 port 時沒有連結', () => {
    expect(jellyfinDetailsUrl({ public_url: '', url: '', port: null }, 'b268', HERE)).toBeNull()
  })

  it('item id 照網址規則編碼', () => {
    expect(
      jellyfinDetailsUrl({ public_url: '', url: 'http://jf', port: null }, 'a b&c', HERE),
    ).toBe('http://jf/web/#/details?id=a%20b%26c')
  })
})

/** 深連結與 Route 設定頁「去 Jellyfin 加路徑」共用的主機推導（票 14a）。 */
describe('jellyfinBase', () => {
  it('後端給了位址就照用', () => {
    expect(jellyfinBase({ public_url: '', url: 'https://jf.example.com', port: null }, HERE)).toBe(
      'https://jf.example.com',
    )
  })

  it('套件內：瀏覽器自己的主機名加 Jellyfin 的 port', () => {
    expect(jellyfinBase({ public_url: '', url: '', port: 8096 }, HERE)).toBe(
      'http://nas.local:8096',
    )
  })

  it('既不知道位址也不知道 port 時是 null，畫面只留文字', () => {
    expect(jellyfinBase({ public_url: '', url: '', port: null }, HERE)).toBeNull()
  })

  // M4 票 54（票 31 實跑抓到，完成頁先修了）：既有 Jellyfin 的位址是 Berth 連過去的那一條。
  it('既有的那一台填 host.docker.internal 時開在瀏覽器的主機名上', () => {
    expect(
      jellyfinBase({ public_url: '', url: 'http://host.docker.internal:8096', port: null }, HERE),
    ).toBe('http://nas.local:8096')
  })

  it('既有的那一台填 compose 主機名時給不出——瀏覽器解不到它', () => {
    expect(
      jellyfinBase({ public_url: '', url: 'http://jellyfin:8096', port: null }, HERE),
    ).toBeNull()
  })

  it('管理員填的對外網址照用，不改寫', () => {
    expect(
      jellyfinBase({ public_url: 'http://jellyfin', url: 'http://jellyfin', port: null }, HERE),
    ).toBe('http://jellyfin')
  })
})

describe('jellyfinLibrariesUrl', () => {
  it('開到 Jellyfin 的媒體庫設定頁', () => {
    expect(jellyfinLibrariesUrl({ public_url: '', url: '', port: 8096 }, HERE)).toBe(
      'http://nas.local:8096/web/#/dashboard/libraries',
    )
  })

  it('推不出主機時沒有連結', () => {
    expect(jellyfinLibrariesUrl({ public_url: '', url: '', port: null }, HERE)).toBeNull()
  })
})

import { describe, expect, it } from 'vitest'

import { jellyfinDetailsUrl } from './jellyfinLink'

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

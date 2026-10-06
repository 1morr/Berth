import { describe, expect, it } from 'vitest'

import { prowlarrWeb, qbittorrentWeb } from './serviceWeb'

const PAGE = { protocol: 'http:', hostname: 'nas.local' }

function setup(origin: 'bundled' | 'existing', base_url: string, web_port: number | null = null) {
  return { origin, kind: 'prowlarr' as const, base_url, web_port }
}

describe('prowlarrWeb', () => {
  it('套件內的那一台開在瀏覽器現在的主機名 + 它發佈的 port，不是容器主機名', () => {
    expect(prowlarrWeb(setup('bundled', 'http://prowlarr:9696', 29696), PAGE)).toBe(
      'http://nas.local:29696',
    )
  })

  it('給不出 port 就沒有連結', () => {
    expect(prowlarrWeb(setup('bundled', 'http://prowlarr:9696'), PAGE)).toBeNull()
  })

  it('既有的那一台用使用者填的位址', () => {
    expect(prowlarrWeb(setup('existing', 'http://192.168.1.10:9696/'), PAGE)).toBe(
      'http://192.168.1.10:9696',
    )
    expect(prowlarrWeb(setup('existing', 'https://nas.example/prowlarr'), PAGE)).toBe(
      'https://nas.example/prowlarr',
    )
  })

  it('既有的填 host.docker.internal：那就是跑 Berth 的這台主機，換成瀏覽器的主機名', () => {
    expect(prowlarrWeb(setup('existing', 'http://host.docker.internal:39696'), PAGE)).toBe(
      'http://nas.local:39696',
    )
  })

  it('瀏覽器解不到的 compose 主機名與解析不了的位址都沒有連結', () => {
    expect(prowlarrWeb(setup('existing', 'http://prowlarr:9696'), PAGE)).toBeNull()
    expect(prowlarrWeb(setup('existing', 'not a url'), PAGE)).toBeNull()
  })
})

describe('qbittorrentWeb（M4 票 26）', () => {
  it('套件內的那一台同樣開在瀏覽器的主機名 + 發佈的 port；給不出 port 就沒有連結', () => {
    const bundled = { origin: 'bundled' as const, base_url: 'http://qbittorrent:8080' }
    expect(qbittorrentWeb({ ...bundled, web_port: 18080 }, PAGE)).toBe('http://nas.local:18080')
    expect(qbittorrentWeb({ ...bundled, web_port: null }, PAGE)).toBeNull()
  })

  it('既有的那一台填的是 compose 主機名就給不出', () => {
    expect(
      qbittorrentWeb(
        { origin: 'existing', base_url: 'http://qbittorrent:8080', web_port: null },
        PAGE,
      ),
    ).toBeNull()
  })
})

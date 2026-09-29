import { describe, expect, it } from 'vitest'

import { pointsAtBerth } from './loopback'

describe('pointsAtBerth（既有服務的位址指到 Berth 自己，M4 票 17）', () => {
  it.each([
    'http://localhost:38096',
    'localhost:8080',
    'https://LOCALHOST/',
    'http://127.0.0.1:9696',
    '127.0.0.1',
    'http://127.0.0.1:8080/api/v2.0/indexers/all/results/torznab/api',
    'http://[::1]:8096',
    '[::1]:8096',
    '::1',
    '  http://localhost:38096  ',
    // 127.0.0.0/8 整段都是迴路。
    'http://127.0.0.10:8096',
  ])('%s 出提示', (address) => {
    expect(pointsAtBerth(address)).toBe(true)
  })

  it.each([
    'http://host.docker.internal:38096',
    'host.docker.internal:38096',
    'http://192.168.1.10:8096',
    '10.0.0.5:8080',
    'http://jellyfin:8096',
    'http://qbittorrent:8080',
    'http://berth-prowlarr:9696',
    'http://nas.local:8096',
    // 長得像但不是：主機名只是含 localhost、或 127 開頭的主機名。
    'http://localhost.example.com:8096',
    'http://mylocalhost:8096',
    'http://127.example.com:8096',
    'http://[::2]:8096',
    '',
    'http://',
  ])('%s 不出', (address) => {
    expect(pointsAtBerth(address)).toBe(false)
  })
})

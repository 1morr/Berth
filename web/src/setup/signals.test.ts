import { describe, expect, it } from 'vitest'

import { chosen, setupStatus } from '../test/fixtures'
import { composeProfiles } from './signals'

describe('composeProfiles（`.env` 的 COMPOSE_PROFILES，M4 票 15）', () => {
  it('什麼都還沒選：選了既有就只拿掉那一個', () => {
    expect(composeProfiles(setupStatus(), 'qbittorrent', 'existing')).toBe(
      'COMPOSE_PROFILES=jellyfin,prowlarr',
    )
  })

  /** code-review 抓到的：寫死整行的話，照著貼會把已經選了既有、拿掉的那一台套件內容器又拉起來。 */
  it('套件內那一台不在 compose 裡：加回它，但不加回別的已經選了既有的', () => {
    const status = setupStatus({
      services: [
        chosen({ kind: 'jellyfin', origin: 'existing', base_url: 'http://nas:8096' }),
        chosen({ kind: 'qbittorrent', state: 'failed', reason: 'not_deployed' }),
      ],
    })

    expect(composeProfiles(status, 'qbittorrent', 'bundled')).toBe(
      'COMPOSE_PROFILES=qbittorrent,prowlarr',
    )
  })

  it('三個都選了既有：那一行是空的', () => {
    const status = setupStatus({
      services: [
        chosen({ kind: 'jellyfin', origin: 'existing' }),
        chosen({ kind: 'qbittorrent', origin: 'existing' }),
      ],
    })

    expect(composeProfiles(status, 'prowlarr', 'existing')).toBe('COMPOSE_PROFILES=')
  })
})

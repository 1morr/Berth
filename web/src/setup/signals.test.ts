import { describe, expect, it } from 'vitest'

import { chosen, setupStatus } from '../test/fixtures'
import { composeProfiles, reasonLabel } from './signals'

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

describe('reasonLabel（連線卡上那一句理由，M4 票 31）', () => {
  it('帳密被拒照服務說：qBittorrent 是帳密，其餘是 API key', () => {
    expect(reasonLabel('qbittorrent', 'auth_required', 'failed')).toBe('reason.auth_required_login')
    expect(reasonLabel('prowlarr', 'auth_required', 'failed')).toBe('reason.auth_required')
    expect(reasonLabel('jellyfin', 'auth_required', 'failed')).toBe('reason.auth_required')
  })

  it('還在等它起來的時候，上一輪的「回的不是它」「連不上」都只是還沒起好', () => {
    expect(reasonLabel('jellyfin', 'protocol_mismatch', 'waiting')).toBe('reason.coming_up')
    expect(reasonLabel('prowlarr', 'unreachable', 'waiting')).toBe('reason.coming_up')
    expect(reasonLabel('jellyfin', 'starting', 'waiting')).toBe('reason.starting')
  })

  it('等完了還是那樣，就照實說', () => {
    expect(reasonLabel('jellyfin', 'protocol_mismatch', 'failed')).toBe('reason.protocol_mismatch')
    expect(reasonLabel('jellyfin', 'unreachable', 'timeout')).toBe('reason.unreachable')
  })
})

import { describe, expect, it } from 'vitest'

import { chosen, setupStatus } from '../test/fixtures'
import { composeProfiles, connectionField, reasonLabel } from './signals'

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

describe('connectionField（測不過的那一次標在哪一格，M4 票 45）', () => {
  it('位址類標在位址欄：連不上、解不到、協定寫錯、回的不是這個服務', () => {
    for (const reason of [
      'unreachable',
      'not_deployed',
      'scheme_mismatch',
      'scheme_missing',
      'protocol_mismatch',
    ] as const) {
      expect(connectionField('qbittorrent', reason)).toBe('address')
    }
  })

  it('憑證類標在憑證欄：帳密或 key 被拒、被封、key 沒填', () => {
    expect(connectionField('qbittorrent', 'auth_required')).toBe('credentials')
    expect(connectionField('qbittorrent', 'ip_banned')).toBe('credentials')
    expect(connectionField('prowlarr', 'auth_required')).toBe('credentials')
    expect(connectionField('prowlarr', 'api_key_missing')).toBe('credentials')
  })

  it('Jellyfin 的表單只有位址：key 被撤不是這張表單的事，留在頁面層級', () => {
    expect(connectionField('jellyfin', 'auth_required')).toBeNull()
    expect(connectionField('jellyfin', 'unreachable')).toBe('address')
  })

  it('其餘留在頁面層級：版本太舊、還在載入、另一台', () => {
    expect(connectionField('qbittorrent', 'version_unsupported')).toBeNull()
    expect(connectionField('jellyfin', 'starting')).toBeNull()
    expect(connectionField('jellyfin', 'other_server')).toBeNull()
  })
})

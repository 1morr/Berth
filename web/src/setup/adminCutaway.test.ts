import { describe, expect, it } from 'vitest'

import { detection } from '../test/fixtures'
import { adminCutaway, detectedOrigin } from './adminCutaway'

const bundled = detection({ kind: 'jellyfin', origin: 'bundled' })
const existing = detection({ kind: 'jellyfin', origin: 'existing', reason: 'setup_completed' })

function lines(overrides: Partial<Parameters<typeof adminCutaway>[0]> = {}) {
  return adminCutaway({
    services: [],
    owned: false,
    applied: true,
    typed: 'skipper',
    owner: 'skipper',
    ...overrides,
  })
}

describe('detectedOrigin', () => {
  it('reads the verdict of that one service', () => {
    expect(detectedOrigin([bundled], 'jellyfin')).toBe('bundled')
    expect(detectedOrigin([existing], 'jellyfin')).toBe('existing')
  })

  it('treats probing, timed out and missing verdicts as not detected yet', () => {
    expect(detectedOrigin([detection({ kind: 'jellyfin', origin: 'pending' })], 'jellyfin')).toBe(
      'undetected',
    )
    expect(detectedOrigin([detection({ kind: 'jellyfin', origin: 'timeout' })], 'jellyfin')).toBe(
      'undetected',
    )
    expect(detectedOrigin([], 'jellyfin')).toBe('undetected')
    expect(detectedOrigin([bundled], 'prowlarr')).toBe('undetected')
  })
})

describe('adminCutaway', () => {
  it('does not promise anything before step 2 has looked', () => {
    const cut = lines()

    expect(cut.jellyfin.key).toBe('admin.cutaway.value.jellyfinPending')
    expect(cut.qbittorrent.key).toBe('admin.cutaway.value.interfacePending')
    expect(cut.prowlarr.key).toBe('admin.cutaway.value.interfacePending')
    expect(cut.berth.key).toBe('admin.cutaway.value.account')
  })

  it('says the whole pair once a service is bundled', () => {
    const services = [
      bundled,
      detection({ kind: 'qbittorrent', origin: 'bundled', reason: 'anonymous_ok' }),
      detection({ kind: 'prowlarr', origin: 'bundled', reason: 'no_indexers' }),
    ]
    const cut = lines({ services })

    expect(cut.jellyfin).toEqual({
      key: 'admin.cutaway.value.pair',
      account: 'skipper',
      muted: false,
    })
    expect(cut.qbittorrent.key).toBe('admin.cutaway.value.pair')
    expect(cut.prowlarr.key).toBe('admin.cutaway.value.pair')
  })

  it('writes nothing to a service that is your own', () => {
    const services = [
      existing,
      detection({ kind: 'qbittorrent', origin: 'existing', reason: 'connected' }),
      detection({ kind: 'prowlarr', origin: 'existing', reason: 'has_indexers' }),
    ]
    const cut = lines({ services, owned: true })

    expect(cut.jellyfin.key).toBe('admin.cutaway.value.jellyfinExisting')
    expect(cut.qbittorrent.key).toBe('admin.cutaway.value.interfaceExisting')
    expect(cut.prowlarr.key).toBe('admin.cutaway.value.interfaceExisting')
    expect(cut.berth.key).toBe('admin.cutaway.value.berthExisting')
  })

  it('says "not applied" for both interfaces when the box is unticked, whatever step 2 found', () => {
    const cut = lines({
      services: [detection({ kind: 'qbittorrent', origin: 'bundled', reason: 'anonymous_ok' })],
      applied: false,
    })

    expect(cut.qbittorrent).toEqual({
      key: 'admin.cutaway.skipped',
      account: 'skipper',
      muted: true,
    })
    expect(cut.prowlarr.key).toBe('admin.cutaway.skipped')
    expect(cut.prowlarr.muted).toBe(true)
  })

  it('keeps the Jellyfin account fixed once Jellyfin owns it and only the interfaces follow the form', () => {
    const cut = lines({ services: [bundled], owned: true, typed: 'deckhand', owner: 'skipper' })

    expect(cut.berth).toEqual({
      key: 'admin.cutaway.value.account',
      account: 'skipper',
      muted: false,
    })
    expect(cut.jellyfin).toEqual({
      key: 'admin.cutaway.value.jellyfinOwned',
      account: 'skipper',
      muted: false,
    })
    expect(cut.qbittorrent.account).toBe('deckhand')
  })
})

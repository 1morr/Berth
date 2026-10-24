import { afterEach, describe, expect, it, vi } from 'vitest'

import { portOffset } from '../e2e/ports.ts'

/**
 * e2e 演練伺服器的 port 整段位移（`E2E_PORT_OFFSET`，`e2e/ports.ts`）：平行的 worktree 各跑一套 e2e 時不搶 port。
 * 讀值的規則，加上 `playwright.config.ts` 真的把每一台替身與它的 `baseURL` 都位移了。
 */
describe('portOffset', () => {
  const PORTS = [8484, 8535]

  it('沒設或空字串是 0', () => {
    expect(portOffset(undefined, PORTS)).toBe(0)
    expect(portOffset('', PORTS)).toBe(0)
  })

  it('整數照收，負的也收', () => {
    expect(portOffset('1000', PORTS)).toBe(1000)
    expect(portOffset('-100', PORTS)).toBe(-100)
  })

  it('不是整數就說清楚', () => {
    expect(() => portOffset('1k', PORTS)).toThrow(/must be an integer/)
    expect(() => portOffset('1.5', PORTS)).toThrow(/must be an integer/)
  })

  it('位移之後落在 1024–65535 之外就說清楚', () => {
    expect(() => portOffset('-8000', PORTS)).toThrow(/outside 1024–65535/)
    expect(() => portOffset('60000', PORTS)).toThrow(/outside 1024–65535/)
  })
})

describe('playwright.config.ts', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  async function load(offset: string | undefined) {
    vi.resetModules()
    if (offset !== undefined) vi.stubEnv('E2E_PORT_OFFSET', offset)
    return (await import('../playwright.config.ts')).default
  }

  /** 每一條流程的 `baseURL` 與它那一台替身的 port，照設定的順序。 */
  async function ports(offset: string | undefined) {
    const config = await load(offset)
    const servers = Array.isArray(config.webServer) ? config.webServer : []
    return {
      base: (config.projects ?? []).map((project) => project.use?.baseURL),
      urls: servers.map((server) => server.url),
      commands: servers.map((server) => /--port (\d+)/.exec(server.command)?.[1]),
    }
  }

  it('不設時 port 照表（CI 不用改）', async () => {
    const { base, urls, commands } = await ports(undefined)
    expect(base[0]).toBe('http://127.0.0.1:8491')
    expect(urls[0]).toBe('http://127.0.0.1:8491/api/health')
    expect(commands[0]).toBe('8491')
  })

  it('設了位移，每一台替身與它的 baseURL 一起平移', async () => {
    const before = await ports(undefined)
    const after = await ports('1000')
    const shift = (url: string | undefined) =>
      url?.replace(/:(\d+)/, (_, port: string) => `:${Number(port) + 1000}`)

    expect(after.base).toEqual(before.base.map(shift))
    expect(after.urls).toEqual(before.urls.map(shift))
    expect(after.commands).toEqual(before.commands.map((port) => String(Number(port) + 1000)))
    expect(after.base.length).toBeGreaterThan(40)
  })
})

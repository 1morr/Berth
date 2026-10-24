import { spawnSync } from 'node:child_process'
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterEach, describe, expect, it } from 'vitest'

/**
 * pre-commit 的 knip 閘門（M4 票 93）：用真正的 `web/knip.json` 對一個暫存的小專案跑 knip CLI。
 * 小專案照 `web/` 的形狀：`gen:api` 叫外部的 `uv`、`src/api/schema.d.ts` 是產生出來的型別檔、
 * 只有 `schemas.ts` 從它取型別。設定裡的白名單被拿掉、或有人開了 `ignoreExportsUsedInFile`，這裡就紅。
 */
const WEB = join(dirname(fileURLToPath(import.meta.url)), '..')
const KNIP = join(WEB, 'node_modules', 'knip', 'bin', 'knip.js')

const TREE: Record<string, string> = {
  'package.json': JSON.stringify({
    name: 'gate-probe',
    private: true,
    type: 'module',
    scripts: { 'gen:api': 'uv run --project .. berth openapi --output openapi.json' },
  }),
  // 產生器的輸出：`paths`、`webhooks`、`operations` 沒有人 import，白名單讓它們不報。
  'src/api/schema.d.ts': `export interface paths { '/api/health': { get: never } }
export type webhooks = Record<string, never>
export interface components { schemas: { HealthOut: { status: string } } }
export type operations = Record<string, never>
`,
  'src/api/schemas.ts': `import type { components } from './schema'

export type Schemas = components['schemas']
`,
  'src/health.ts': `import type { Schemas } from './api/schemas'

export function statusOf(health: Schemas['HealthOut']): string {
  return health.status
}
`,
  'src/index.ts': `import { statusOf } from './health'

console.log(statusOf({ status: 'ok' }))
`,
}

let root: string | undefined

function probe(changes: Record<string, string> = {}): string {
  root = mkdtempSync(join(tmpdir(), 'berth-knip-'))
  for (const [path, text] of Object.entries({ ...TREE, ...changes })) {
    mkdirSync(dirname(join(root, path)), { recursive: true })
    writeFileSync(join(root, path), text)
  }
  copyFileSync(join(WEB, 'knip.json'), join(root, 'knip.json'))
  return root
}

/** knip 報的每一條，`<種類>:<名字>`；外加離開碼，閘門靠的是它。 */
function knip(directory: string): { status: number | null; reported: string[] } {
  const run = spawnSync(
    process.execPath,
    [KNIP, '--directory', directory, '--no-progress', '--reporter', 'json'],
    { encoding: 'utf8' },
  )
  const report = JSON.parse(run.stdout) as { issues: Record<string, unknown>[] }
  const reported = report.issues.flatMap((issue) =>
    Object.entries(issue).flatMap(([kind, items]) =>
      Array.isArray(items) ? items.map((item: { name: string }) => `${kind}:${item.name}`) : [],
    ),
  )
  return { status: run.status, reported }
}

afterEach(() => {
  if (root) rmSync(root, { recursive: true, force: true })
  root = undefined
})

describe('knip 閘門', () => {
  it('沒有人 import 的 export 會報', { timeout: 60_000 }, () => {
    const result = knip(
      probe({
        'src/health.ts': `${TREE['src/health.ts']}
export const HEALTH_LABEL = 'health'
`,
      }),
    )

    expect(result.reported).toEqual(['exports:HEALTH_LABEL'])
    expect(result.status).not.toBe(0)
  })

  it('只在同一個檔裡用到的 export 也報：export 面保持最小', { timeout: 60_000 }, () => {
    const result = knip(
      probe({
        'src/health.ts': `import type { Schemas } from './api/schemas'

export const UNKNOWN = 'unknown'

export function statusOf(health: Schemas['HealthOut']): string {
  return health.status || UNKNOWN
}
`,
      }),
    )

    expect(result.reported).toEqual(['exports:UNKNOWN'])
    expect(result.status).not.toBe(0)
  })

  it('合規的樹不報：外部的 uv、產生出來的型別檔不算', { timeout: 60_000 }, () => {
    expect(knip(probe())).toEqual({ status: 0, reported: [] })
  })

  // 同一棵樹換了名字與排版，沒有多出沒人用的東西。
  it('改名字、改排版不會讓它紅', { timeout: 60_000 }, () => {
    const result = knip(
      probe({
        'src/health.ts': `import type { Schemas } from './api/schemas'

export function describeHealth(
  health: Schemas['HealthOut'],
): string {
  return \`health: \${health.status}\`
}
`,
        'src/index.ts': `import { describeHealth } from './health'

const line = describeHealth({ status: 'ok' })
console.log(line)
`,
      }),
    )

    expect(result).toEqual({ status: 0, reported: [] })
  })
})

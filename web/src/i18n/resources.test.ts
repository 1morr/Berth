import { describe, expect, it } from 'vitest'
import ts from 'typescript'

import { resources, SUPPORTED_LANGUAGES } from './resources'

type Tree = { readonly [key: string]: string | Tree }

/**
 * 值裡帶 `{{count}}`、卻不是 `_one` / `_other` 一對的鍵。
 *
 * i18next 收到 `count` 時查的是 `key_one` / `key_other`，兩個都沒有就退回原鍵——於是英文在只有一筆時
 * 說「1 routes」，而且沒有任何東西會紅（CHANGELOG 記過探索頁的那一個，票 15 收掉其餘的）。
 * 中文的兩個值通常一樣，照樣要成對：規則對兩個語言是同一條，鍵樹才對得起來。
 */
function pluralGaps(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value !== 'string') return pluralGaps(value, path)
    if (!value.includes('{{count}}')) return []
    const base = key.replace(/_(one|other)$/, '')
    const paired = base !== key && `${base}_one` in tree && `${base}_other` in tree
    return paired ? [] : [path]
  })
}

describe('plural keys', () => {
  it.each(SUPPORTED_LANGUAGES)('every count in %s has a _one and an _other', (language) => {
    expect(pluralGaps(resources[language].translation)).toEqual([])
  })

  it('catches a count that has no plural pair', () => {
    expect(pluralGaps({ health: { routes: { count: '{{count}} routes' } } })).toEqual([
      'health.routes.count',
    ])
  })

  it('catches half a pair', () => {
    expect(pluralGaps({ drift: { changed_one: '{{count}} key differs' } })).toEqual([
      'drift.changed_one',
    ])
  })

  it('leaves pairs, other placeholders and plain strings alone wherever they sit', () => {
    expect(
      pluralGaps({
        files_one: '{{count}} file',
        files_other: '{{count}} files',
        deep: {
          nested: {
            idle_one: '{{count}} minute quiet',
            idle_other: '{{count}} minutes quiet',
          },
        },
        done: 'Deleted “{{name}}”.',
        title: 'Library routes',
      }),
    ).toEqual([])
  })
})

/**
 * 寫死檢查條數的文案（M4 票 31）。
 *
 * Route 的檢查從五條長成六條（M4 票 19 加了 `download_visible`），七個鍵還寫著「五條纜繩」——條數住在
 * `CHECK_LABEL`，文案不跟著它改。所以文案不寫條數；要數字就用 `{{count}}` 從程式帶進來。
 * 「一條」不算：「每一條」「哪一條纜繩」說的是其中一條，不是總數。
 */
const COUNTED_CHECKS =
  /[二兩三四五六七八九十\d]+\s*條(纜繩|檢查)|\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(checks|cables)\b/i

function countedChecks(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value !== 'string') return countedChecks(value, path)
    return COUNTED_CHECKS.test(value) ? [path] : []
  })
}

describe('route check counts', () => {
  it.each(SUPPORTED_LANGUAGES)('no %s copy writes down how many checks a route has', (language) => {
    expect(countedChecks(resources[language].translation)).toEqual([])
  })

  it('catches a fixed count in either language', () => {
    expect(
      countedChecks({
        zh: { rerun: '啟用時會先把五條纜繩重跑一次。', six: '六條檢查都要綠燈' },
        en: { rerun: 'Enabling it runs the five checks again.', digits: 'all 6 checks passed' },
      }),
    ).toEqual(['zh.rerun', 'zh.six', 'en.rerun', 'en.digits'])
  })

  it('leaves counted placeholders, berths and other counts alone', () => {
    expect(
      countedChecks({
        passed: '{{passed}} / {{total}} 通過',
        berths: '五個泊位都走過了。',
        enBerths: 'All five berths have been visited.',
        every: '每一條 Route 的每一條纜繩都要綠燈。',
        which: '到健康頁看是哪一條纜繩斷了。',
        counted: '{{count}} checks failed',
        sites: 'Prowlarr already has 5 sites.',
      }),
    ).toEqual([])
  })
})

/**
 * 沒有引用處的鍵（M4 票 54）。
 *
 * 畫面改掉之後鍵留在這裡，下一個人改文案時就在改沒人看得到的句子（`jellyfin.fix.configuration` 還寫著
 * 「語言設成繁體中文」，語言早就跟著介面或由人選，審計 §A3）。所以每個鍵都要在原始碼裡寫得出來：
 *
 * - 字面值（`t('a.b')`、查表的值）照字比；
 * - 樣板字串（`` t(`indexer.lede.${origin}`) ``）的 `${…}` 換成「任一段鍵」，開頭要是 `命名空間.`——
 *   `` `${a}.${b}` `` 什麼都比得上，不算；
 * - 複數鍵（`_one` / `_other`）比的是去掉字尾的那一個，i18next 收到 `count` 時自己接上。
 *
 * 字串從 TypeScript 的語法樹取，註解裡提到的鍵不算引用。**這條擋不住的**：查表裡寫了、卻從來沒有被讀的
 * 那一格——表本身就是引用處（票 54 刪掉的 `jellyfin.step.*` 六格就是這樣漏過的，呼叫端只讀 `.libraries`）。
 */
function keyReferences(sources: readonly string[]) {
  const literals = new Set<string>()
  const patterns: RegExp[] = []
  const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  function visit(node: ts.Node) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      literals.add(node.text)
    } else if (ts.isTemplateExpression(node) && /^[a-zA-Z]\w*\./.test(node.head.text)) {
      const parts = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)]
      patterns.push(new RegExp(`^${parts.map(escape).join('[\\w.-]+')}$`))
    }
    ts.forEachChild(node, visit)
  }
  for (const source of sources) {
    visit(
      ts.createSourceFile('source.tsx', source, ts.ScriptTarget.Latest, false, ts.ScriptKind.TSX),
    )
  }
  return { literals, patterns }
}

function unreferencedKeys(tree: Tree, sources: readonly string[]): string[] {
  const { literals, patterns } = keyReferences(sources)
  const keys = (branch: Tree, prefix = ''): string[] =>
    Object.entries(branch).flatMap(([key, value]) => {
      const path = prefix ? `${prefix}.${key}` : key
      return typeof value === 'string' ? [path] : keys(value, path)
    })
  return keys(tree).filter((path) => {
    const key = path.replace(/_(zero|one|two|few|many|other)$/, '')
    return !literals.has(key) && !patterns.some((pattern) => pattern.test(key))
  })
}

/** 產品原始碼：測試檔與鍵樹自己不算引用處。 */
const PRODUCT_SOURCES = import.meta.glob<string>(
  ['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!./resources.ts'],
  { query: '?raw', import: 'default', eager: true },
)

describe('unreferenced keys', () => {
  it('every key is written somewhere in the product source', () => {
    expect(Object.keys(PRODUCT_SOURCES).length).toBeGreaterThan(100)
    expect(
      unreferencedKeys(resources['zh-Hant'].translation, Object.values(PRODUCT_SOURCES)),
    ).toEqual([])
  })

  it('catches a key nothing asks for, even when a comment mentions it', () => {
    expect(
      unreferencedKeys({ owner: { saved: '已存下', title: '擁有者' } }, [
        "// owner.saved 以前在這裡用\nconst title = t('owner.title')",
      ]),
    ).toEqual(['owner.saved'])
  })

  it('does not care how a reference is written', () => {
    expect(
      unreferencedKeys(
        {
          indexer: { lede: { bundled: 'a', existing: 'b' } },
          reason: { coming_up: 'c' },
          stage: { berth: 'd' },
          jobs: { files_one: 'e', files_other: 'f' },
        },
        [
          [
            'const lede = t(`indexer.lede.${origin}`)',
            'const LABEL = { waiting: "reason.coming_up" } as const',
            "const line = `${t('stage.berth', { code })} · ${step}`",
            't(\n  "jobs.files",\n  { count },\n)',
          ].join('\n'),
        ],
      ),
    ).toEqual([])
  })

  it('does not let a template with no namespace stand for every key', () => {
    expect(unreferencedKeys({ a: { b: 'x' } }, ['const key = `${scope}.${name}`'])).toEqual(['a.b'])
  })
})

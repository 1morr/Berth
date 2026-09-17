import { describe, expect, it } from 'vitest'

/**
 * 長字串怎麼換行（DESIGN.md 的 Layout 與 Do's and Don'ts，票 15）。
 *
 * - **機器字串（`.value`）用 `wrap-anywhere`**：`break-words` 不改 flex / grid 子項的最小寬度，
 *   沒有空格的發佈名在 390px 上把 `/jobs` 撐出 67px 的整頁橫向捲動（票 15 實測）。
 * - **不用 `break-all`**：它連英文詞中間都斷（`(S` / `TEP 4)`）。
 * - 散文照舊 `break-words`——它在詞與詞之間斷，而散文一定有空格。
 */
function wrappingViolations(source: string): string[] {
  const classNames = source.match(/className=(?:"[^"]*"|\{`[^`]*`\})/g) ?? []
  return classNames.filter(
    (name) =>
      /\bbreak-all\b/.test(name) ||
      (/(?<![\w-])value(?![\w-])/.test(name) && /\bbreak-words\b/.test(name)),
  )
}

const SOURCES = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

describe('long strings wrap the way DESIGN.md says', () => {
  it('no component breaks a machine string with break-words or anything with break-all', () => {
    const found = Object.entries(SOURCES).flatMap(([path, source]) =>
      wrappingViolations(source).map((name) => `${path}: ${name}`),
    )

    expect(Object.keys(SOURCES).length).toBeGreaterThan(20)
    expect(found).toEqual([])
  })

  it('catches a machine string that only breaks between words', () => {
    expect(wrappingViolations('<p className="value text-xs break-words">x</p>')).toHaveLength(1)
    expect(
      wrappingViolations('<p className={`value text-xs break-words ${tone}`}>x</p>'),
    ).toHaveLength(1)
  })

  it('catches break-all anywhere', () => {
    expect(wrappingViolations('<span className="block break-all">x</span>')).toHaveLength(1)
  })

  it('leaves prose, wrap-anywhere and look-alike class names alone', () => {
    expect(
      wrappingViolations(
        [
          '<p className="max-w-prose text-xs break-words">prose</p>',
          '<p className="value text-xs wrap-anywhere">machine</p>',
          '<p className={`values-grid break-words ${tone}`}>not the value class</p>',
          '<p className="label value-small break-words">still not .value</p>',
        ].join('\n'),
      ),
    ).toEqual([])
  })
})

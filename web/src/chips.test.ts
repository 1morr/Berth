import { describe, expect, it } from 'vitest'

/**
 * 狀態色塊只有三種內距（DESIGN.md Chips）：標準 `px-2 py-1.5`、compact `px-1.5 py-0.5`、時間線
 * `px-1.5 py-1`。M4 票 92 之前漂出了第四種 `px-2 py-1`（11 處，使用者 2026-10-13 定為 compact）。
 *
 * 認的是塗了底的 `.label`（`SIGNAL_FILL` / `UNPAINTED_FILL` / `bg-deck`）上色塊大小的內距（`px-1.5`、`px-2`）；
 * 面板抬頭列的 `px-4` 不是色塊。沒有 class 排序器，所以不靠 `px` 與 `py` 相鄰：類名照字串片段切開
 * （`compact ? 'px-1.5 py-0.5' : 'px-2 py-1.5'` 的兩段各是一組），同一段裡的 `px` 與 `py` 配成一對。
 */
const CHIP_PADDINGS = new Set(['px-2 py-1.5', 'px-1.5 py-0.5', 'px-1.5 py-1'])

function chipPaddingViolations(source: string): string[] {
  const classNames = source.match(/className=(?:"[^"]*"|\{`[^`]*`\})/g) ?? []
  return classNames.filter((name) => {
    if (!/(?<![\w-])label(?![\w-])/.test(name)) return false
    if (!/\b(?:SIGNAL_FILL|UNPAINTED_FILL|bg-deck)\b/.test(name)) return false
    return name.split(/['"`?:{}$]/).some((segment) => {
      const px = /(?<![\w-])px-(?:1\.5|2)(?![\w.-])/.exec(segment)?.[0]
      if (!px) return false
      const py = /(?<![\w-])py-[\d.]+(?![\w.-])/.exec(segment)?.[0]
      return !CHIP_PADDINGS.has(`${px} ${py}`)
    })
  })
}

const SOURCES = import.meta.glob<string>(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

describe('status chips use one of the three paddings DESIGN.md names', () => {
  it('no filled .label chip drifts to a fourth padding', () => {
    const found = Object.entries(SOURCES).flatMap(([path, source]) =>
      chipPaddingViolations(source).map((name) => `${path}: ${name}`),
    )

    expect(Object.keys(SOURCES).length).toBeGreaterThan(20)
    expect(found).toEqual([])
  })

  it('catches the drifted padding on a signal chip and on a neutral one', () => {
    expect(
      chipPaddingViolations('<span className={`label px-2 py-1 ${SIGNAL_FILL.assigned}`}>x</span>'),
    ).toHaveLength(1)
    expect(
      chipPaddingViolations('<span className="label bg-deck px-2 py-1 text-ink">x</span>'),
    ).toHaveLength(1)
    // 換了順序、中間夾了別的 class 也一樣。
    expect(
      chipPaddingViolations('<span className="label py-1 mr-3 px-2 bg-deck text-ink">x</span>'),
    ).toHaveLength(1)
    expect(
      chipPaddingViolations(
        "<span className={`label ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1'} ${SIGNAL_FILL.secured}`}>x</span>",
      ),
    ).toHaveLength(1)
  })

  it('leaves the three named paddings, panel headers and unfilled boxes alone', () => {
    expect(
      chipPaddingViolations(
        [
          '<span className={`label px-2 py-1.5 ${SIGNAL_FILL.working}`}>x</span>',
          '<span className="label bg-deck px-1.5 py-0.5 text-ink">x</span>',
          '<span className="label bg-deck px-1.5 py-1 text-ink">x</span>',
          '<span className="label py-0.5 shrink-0 px-1.5 bg-deck text-ink">x</span>',
          "<span className={`label shrink-0 ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1.5'} ${SIGNAL_FILL.assigned}`}>x</span>",
          '<h2 className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink">x</h2>',
          '<span className="label border-2 border-rule px-2 py-1 text-ink-dim">x</span>',
          '<a className="label-ish bg-deck px-2 py-1 text-ink">x</a>',
        ].join('\n'),
      ),
    ).toEqual([])
  })
})

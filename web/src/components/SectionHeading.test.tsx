import { render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it } from 'vitest'

import { SectionHeading } from './SectionHeading'

describe('SectionHeading', () => {
  it('看得見的是數字，聽得見的是帶單位的那一句（DESIGN.md 區塊標題）', () => {
    render(
      <SectionHeading id="files" label="檔案與版本" count={{ value: 3, spoken: '共 3 個檔案' }} />,
    )

    expect(screen.getByRole('heading', { level: 2, name: '檔案與版本' })).toHaveAttribute(
      'id',
      'files',
    )
    expect(screen.getByText('3')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('共 3 個檔案')).toHaveClass('sr-only')
  })

  it('給了 headingRef 才送得進焦點，而且不進 Tab 順序', () => {
    const ref = createRef<HTMLHeadingElement>()
    const { rerender } = render(<SectionHeading id="search" label="搜尋" headingRef={ref} />)

    expect(ref.current).toBe(screen.getByRole('heading', { name: '搜尋' }))
    expect(ref.current).toHaveAttribute('tabindex', '-1')

    rerender(<SectionHeading id="search" label="搜尋" />)
    expect(screen.getByRole('heading', { name: '搜尋' })).not.toHaveAttribute('tabindex')
  })
})

/**
 * 頁內的區塊標題只有 `SectionHeading` 一份（M4 票 92）：手寫的那幾份曾經把計數寫成裸數字，螢幕閱讀器只念「3」。
 * 認的是 `.label` 模板字的 `<h2>`；面板的 `deck` 抬頭列（健康頁的卡片）是另一種東西，不算。
 */
function handWrittenSectionHeadings(source: string): string[] {
  const openings = source.match(/<h2\b[^>]*>/g) ?? []
  return openings.filter((tag) => {
    const name = /className=(?:"[^"]*"|\{`[^`]*`\}|\{[^}]*\})/.exec(tag)?.[0] ?? ''
    return /(?<![\w-])label(?![\w-])/.test(name) && !/\bbg-deck\b/.test(name)
  })
}

const SOURCES = import.meta.glob<string>(
  ['../**/*.tsx', '!../**/*.test.tsx', '!./SectionHeading.tsx'],
  { query: '?raw', import: 'default', eager: true },
)

describe('section headings live in one place', () => {
  it('no component hand-writes a .label section heading outside SectionHeading', () => {
    const found = Object.entries(SOURCES).flatMap(([path, source]) =>
      handWrittenSectionHeadings(source).map((tag) => `${path}: ${tag}`),
    )

    expect(Object.keys(SOURCES).length).toBeGreaterThan(20)
    expect(found).toEqual([])
  })

  it('catches a hand-written heading however its attributes are laid out', () => {
    expect(handWrittenSectionHeadings('<h2 id={id} className="label text-ink">')).toHaveLength(1)
    expect(
      handWrittenSectionHeadings(
        '<h2\n  id={headingId}\n  ref={heading}\n  tabIndex={-1}\n  className="label text-ink"\n>',
      ),
    ).toHaveLength(1)
    expect(
      handWrittenSectionHeadings(
        '<h2 className="label border-b-2 border-rule-strong pb-2 text-ink">',
      ),
    ).toHaveLength(1)
    expect(handWrittenSectionHeadings('<h2 className={`label ${tone}`}>')).toHaveLength(1)
  })

  it('leaves panel header rows, other heading styles and look-alike classes alone', () => {
    expect(
      handWrittenSectionHeadings(
        [
          '<h2 id="health-budget" className="label border-b-2 border-rule bg-deck px-4 py-2.5 text-ink">',
          '<h2 id={id} className="value text-sm font-semibold text-ink">',
          '<h2 className="text-lg font-semibold text-ink">',
          '<h2 className="labelled-row text-ink">',
          '<h3 className="label text-ink">',
        ].join('\n'),
      ),
    ).toEqual([])
  })
})

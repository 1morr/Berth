import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

/**
 * `eslint.config.js` 裡擋 JSX 註解外露的那一條（M4 票 10）：精靈第 2 步把 `// …` 寫在子節點裡，
 * 畫面上就印出那一行。這裡用真正的設定檔跑，拿掉那一條、或外掛沒接上，第一個測試就會紅。
 */
const RULE = '@eslint-react/jsx-no-comment-textnodes'

// 型別資訊要一個專案裡真的有的檔名；內容是這裡給的，檔案本身不讀。
const PROBE = 'src/setup/StepFrame.tsx'

async function flagged(source: string): Promise<string[]> {
  const [result] = await new ESLint().lintText(source, { filePath: PROBE })
  return result.messages.filter((message) => message.ruleId === RULE).map((m) => m.message)
}

describe('JSX 子節點裡的註解', () => {
  it('寫成 `// …` 的會被擋：那一行會印在畫面上', { timeout: 60_000 }, async () => {
    const source = `export function Probe() {
  return (
    <div>
      // 焦點接到這一顆
      <button type="button">Go</button>
    </div>
  )
}
`
    expect(await flagged(source)).toHaveLength(1)
  })

  // 同一段換了名字與排版；`//` 還在，只是在大括號、字串與屬性裡——這些不會印成那一行字。
  it('包在大括號裡、或只是字串裡有 `//` 的不會', { timeout: 60_000 }, async () => {
    const source = `export function Continue({ host }: { host: string }) {
  return (
    <section className="grid">
      {/* 焦點接到這一顆 */}
      {'// 這是字'}
      <a href={\`https://\${host}/web\`}>Jellyfin</a>
      <button type="button">Next</button>
    </section>
  )
}
`
    expect(await flagged(source)).toEqual([])
  })
})

/**
 * 後端原文不當標題（M4 票 21）：`eslint.config.js` 的 `no-restricted-syntax` 只管精靈、設定頁、健康頁與
 * 共用元件。用真正的設定檔跑——規則被拿掉、範圍的 glob 寫錯、或 selector 認不出換了包法的同一件事，
 * 第一組就會紅；第二組是合規的寫法（原文經 `TechnicalDetails` 的屬性、或只拿來判斷）換了排版與名字，
 * 不該紅。**擋不到的**：先賦值給變數再畫、塞進 `t()` 的插值——規則只認直接畫成子節點的成員存取。
 */
const RAW_TEXT = 'no-restricted-syntax'

async function rawText(source: string, filePath = PROBE): Promise<number> {
  const [result] = await new ESLint().lintText(source, { filePath })
  return result.messages.filter((message) => message.ruleId === RAW_TEXT).length
}

describe('後端原文不當標題', () => {
  it('把 `.error` / `.message` 直接畫成子節點會被擋，不管怎麼包', { timeout: 60_000 }, async () => {
    const source = `export function Probe({ row, failure }: { row?: { error: string }; failure: Error }) {
  return (
    <div>
      <p role="alert">{row?.error}</p>
      <>{failure.message}</>
      <span>{row && row.error}</span>
      <span>{row ? row.error : ''}</span>
    </div>
  )
}
`
    expect(await rawText(source)).toBe(4)
  })

  it(
    '原文經 TechnicalDetails 的屬性進畫面、或只拿來判斷，不會被擋',
    { timeout: 60_000 },
    async () => {
      const source = `import { TechnicalDetails } from '../components/TechnicalDetails'

export function Line({ step }: { step: { error: string; failure: string | null } }) {
  const shown = step.error !== ''
  return (
    <section>
      {step.error && (
        <TechnicalDetails
          lines={[ step.error ]}
        />
      )}
      {shown ? <p>{step.failure}</p> : null}
    </section>
  )
}
`
      expect(await rawText(source)).toBe(0)
    },
  )

  it(
    '範圍之外的頁（Job 的時間線是入庫的原因，不是設定錯誤）不管',
    { timeout: 60_000 },
    async () => {
      const source = `export function Probe({ row }: { row: { error: string } }) {
  return <p>{row.error}</p>
}
`
      expect(await rawText(source, 'src/jobs/JobTimeline.tsx')).toBe(0)
    },
  )
})

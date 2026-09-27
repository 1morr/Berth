import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

/**
 * `eslint.config.js` 裡擋 JSX 註解外露的那一條（M4 票 10）：精靈第 2 步把 `// …` 寫在子節點裡，
 * 畫面上就印出那一行。這裡用真正的設定檔跑，拿掉那一條、或外掛沒接上，第一個測試就會紅。
 */
const RULE = '@eslint-react/jsx-no-comment-textnodes'

// 型別資訊要一個專案裡真的有的檔名；內容是這裡給的，檔案本身不讀。
const PROBE = 'src/setup/DetectStep.tsx'

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

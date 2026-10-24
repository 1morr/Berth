import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { UsageTally } from '../api/ai'
import { useUsageFormat } from './usageFormat'

export interface UsageLine {
  key: string
  /** 第一欄：出處、模型、人或日期。 */
  label: ReactNode
  /** 第一欄是人話（出處、「沒有人」）：走散文的字與斷行，不是 `.value wrap-anywhere`（DESIGN.md 的 Do 段）。 */
  prose?: boolean
  /** 第一欄底下的一行機器字串（格式 · 主機）。 */
  sub?: string
  tally: UsageTally
}

/**
 * 窄版收掉的四欄，改到第一欄底下（DESIGN.md〈窄版的收法〉：一份 DOM 兩種版面）。一組一行，不用一行中點分隔：
 * 四組「名字 數字」在 390 寬一定會斷行，斷開的那一行以中點開頭，讀起來像清單符號（實跑看到的）。
 */
const TOKEN_COLUMNS = ['input', 'output', 'cacheWrite', 'cacheRead'] as const

const CELL = 'value px-3 py-2 text-right text-sm'

/** 用量頁的每一張表（含沒成的那一張）共用的外框與欄名。 */
export const USAGE_TABLE = 'w-full border-collapse border-2 border-rule bg-well text-left'
export const HEAD_CELL = 'label px-3 py-2 whitespace-nowrap text-ink-dim'

/**
 * 用量的一張表：依出處、格式與模型、人，與逐日數字共用（M5 票 13）。命中率那一格底下說這一列有幾次沒回報快取，
 * 命中率因此少算了它們。表名由外面的區塊標題給（`labelledBy`）。
 */
export function UsageTable({
  labelledBy,
  first,
  lines,
}: {
  labelledBy: string
  /** 第一欄的欄名。 */
  first: string
  lines: readonly UsageLine[]
}) {
  const { t } = useTranslation()
  const format = useUsageFormat()

  return (
    <table aria-labelledby={labelledBy} className={USAGE_TABLE}>
      <thead>
        <tr>
          <th scope="col" className={HEAD_CELL}>
            {first}
          </th>
          <th scope="col" className={`${HEAD_CELL} text-right`}>
            {t('settings.usagePage.column.calls')}
          </th>
          {TOKEN_COLUMNS.map((column) => (
            <th key={column} scope="col" className={`${HEAD_CELL} hidden text-right sm:table-cell`}>
              {t(`settings.usagePage.column.${column}`)}
            </th>
          ))}
          <th scope="col" className={`${HEAD_CELL} text-right`}>
            {t('settings.usagePage.column.hitRate')}
          </th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => {
          const tokens = {
            input: line.tally.input_tokens,
            output: line.tally.output_tokens,
            cacheWrite: line.tally.cache_write_tokens,
            cacheRead: line.tally.cache_read_tokens,
          }
          return (
            <tr key={line.key} className="border-t-2 border-rule align-top">
              <th scope="row" className="min-w-0 px-3 py-2 text-sm font-normal text-ink">
                <span className={line.prose ? 'break-words' : 'value wrap-anywhere'}>
                  {line.label}
                </span>
                {line.sub && (
                  <span className="value block text-xs wrap-anywhere text-ink-dim">{line.sub}</span>
                )}
                <span className="value mt-1 grid text-xs text-ink-dim sm:hidden">
                  {TOKEN_COLUMNS.map((column) => (
                    // 一組不拆開（「Cache write」與它的數字在 390 寬曾分成兩行）。
                    <span key={column} className="whitespace-nowrap">
                      {t(`settings.usagePage.column.${column}`)} {format.count(tokens[column])}
                    </span>
                  ))}
                </span>
              </th>
              <td className={CELL}>{format.count(line.tally.calls)}</td>
              {TOKEN_COLUMNS.map((column) => (
                <td key={column} className={`${CELL} hidden sm:table-cell`}>
                  {format.count(tokens[column])}
                </td>
              ))}
              <td className={CELL}>
                {format.rate(line.tally.hit_rate)}
                {line.tally.cache_unreported > 0 && (
                  // 窄版可以換行：不換行的「13 unreported」把第一欄擠窄，模型 id 從字中間斷開（M5 票 15）。
                  <span className="block text-xs text-ink-dim sm:whitespace-nowrap">
                    {t('settings.usagePage.unreportedShort', {
                      count: line.tally.cache_unreported,
                    })}
                  </span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

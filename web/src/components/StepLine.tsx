import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { SetupStep, StepStatus } from '../api/schemas'
import { CopyLine } from './controls'
import { failureText } from './failures'
import { SIGNAL_FILL } from './signal'
import { STATUS_LABEL, STATUS_SIGNAL } from './steps'
import { TechnicalDetails } from './TechnicalDetails'

/**
 * 一條纜繩：靠泊序列裡的一個步驟（direction contract 的署名互動）。
 *
 * 每個泊位的步驟集合不同，但形狀完全一樣：色塊 + 模板字狀態 + 名稱 + 關鍵值；失敗**就地**變紅並展開
 * 一句人話、補法與可複製的手動步驟，其餘已繫上的纜繩不動。
 *
 * **錯誤分三層**（M4 票 21，`.scratch/m4/error-layers-shape.md`）：人話由後端的代碼（`row.failure`）選，
 * 不是後端的英文；補法由呼叫端照代碼與來源給；端點、實測值與原文收進「技術細節」——通過的那一列
 * 放在行尾，失敗的那一列放在補法之後。
 */
export function StepLine({
  label,
  service,
  endpoint,
  summary,
  row,
  status: statusText,
  fix,
  commands = [],
  children,
}: {
  label: string
  /** 造成失敗的那一台（「連不到 qBittorrent」）。人話裡的 `{{service}}`。 */
  service?: string
  /** 這一步真的打的那支端點，或它寫的那個鍵。收進技術細節。 */
  endpoint?: string
  /**
   * 貼在行首的關鍵值（路徑、分類名、筆數）。沒給就沒有：`row.detail` 是後端的實測值，收進技術細節。
   */
  summary?: string
  row: SetupStep | undefined
  /**
   * 換掉色塊上那個狀態字。`pending` 一律是「尚未執行」，但有的纜繩的待處理不是「還沒跑」：既有 Prowlarr
   * 連上了而 0 站是「還沒有站」（M4 票 31）。色塊照舊由狀態決定。
   */
  status?: string
  /** 失敗時的補法。手動步驟本身在 `commands`。 */
  fix?: string
  commands?: readonly string[]
  /** 失敗區塊裡補法之後的補充（例如「重試只會跑沒完成的那幾步」）。 */
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const status: StepStatus = row?.status ?? 'pending'
  const failed = status === 'failed' && row !== undefined
  // 行首已經貼著的值不在技術細節裡再列一次（搜尋那一排的筆數就是 `detail`）。
  const technical = [endpoint, row?.detail !== summary ? row?.detail : null, row?.error]

  return (
    <li
      className={`min-w-0 border-2 bg-well ${failed ? 'border-rule-strong' : 'border-rule'}`}
      data-failure={failed ? (row.failure ?? 'unexpected') : undefined}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[STATUS_SIGNAL[status]]}`}>
          {statusText ?? t(STATUS_LABEL[status])}
        </span>
        <span className="value text-sm font-semibold text-ink">{label}</span>
        {summary && <span className="value text-xs wrap-anywhere text-ink">{summary}</span>}
        {!failed && <TechnicalDetails inline lines={technical} />}
      </div>

      {failed && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p role="alert" className="max-w-prose text-sm text-blocked-ink">
            {failureText(t, row, service ?? label)}
          </p>
          {fix && (
            <>
              <h5 className="label mt-4 text-ink-dim">{t('connect.fix.title')}</h5>
              <p className="mt-2 max-w-prose text-xs text-ink-dim">{fix}</p>
            </>
          )}
          {commands.length > 0 && (
            <div className="mt-2 grid grid-cols-1 gap-px">
              {commands.map((command) => (
                <CopyLine key={command} command={command} />
              ))}
            </div>
          )}
          {children}
          <TechnicalDetails lines={technical} />
        </div>
      )}
    </li>
  )
}

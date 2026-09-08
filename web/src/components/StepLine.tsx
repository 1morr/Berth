import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { SetupStep, StepStatus } from '../api/schemas'
import { CopyLine } from './controls'
import { SIGNAL_FILL } from './signal'
import { STATUS_LABEL, STATUS_SIGNAL } from './steps'

/**
 * 一條纜繩：靠泊序列裡的一個步驟（direction contract 的署名互動）。
 *
 * 每個泊位的步驟集合不同，但形狀完全一樣：色塊 + 模板字狀態 + 名稱 + 實測值 + 它打的端點；
 * 失敗**就地**變紅並展開可複製的手動步驟，其餘已繫上的纜繩不動。
 */

export function StepLine({
  label,
  endpoint,
  row,
  fix,
  commands = [],
  children,
}: {
  label: string
  /** 這一步真的打的那支端點，或它寫的那個鍵。貼在它那一行，不進散文。 */
  endpoint?: string
  row: SetupStep | undefined
  /** 失敗時的說明。手動步驟本身在 `commands`。 */
  fix?: string
  commands?: readonly string[]
  /** 失敗區塊末尾的補充（例如「重試只會跑沒完成的那幾步」）。 */
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const status: StepStatus = row?.status ?? 'pending'

  return (
    <li
      className={`min-w-0 border-2 bg-well ${
        status === 'failed' ? 'border-rule-strong' : 'border-rule'
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className={`label px-2 py-1.5 ${SIGNAL_FILL[STATUS_SIGNAL[status]]}`}>
          {t(STATUS_LABEL[status])}
        </span>
        <span className="value text-sm font-semibold text-ink">{label}</span>
        {row?.detail && <span className="value text-xs text-ink">{row.detail}</span>}
        {endpoint && (
          <span className="value ml-auto min-w-0 truncate text-xs text-ink-dim">{endpoint}</span>
        )}
      </div>

      {status === 'failed' && row && (
        <div className="border-t-2 border-rule bg-hull px-4 py-4">
          <p role="alert" className="value max-w-prose break-words text-xs text-blocked-ink">
            {row.error}
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
        </div>
      )}
    </li>
  )
}

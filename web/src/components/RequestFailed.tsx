import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { Notice } from './controls'
import { PROBLEM_TEXT, requestProblem } from './requestProblem'
import { TechnicalDetails } from './TechnicalDetails'

/** 技術細節：狀態碼、端點，以及後端的 `detail`（422 是欄位錯誤的清單）。 */
function technicalOf(error: unknown): string[] {
  if (!(error instanceof ApiError)) return [error instanceof Error ? error.message : String(error)]
  const detail = error.detail
  return [
    error.message,
    typeof detail === 'string' ? detail : detail === undefined ? '' : JSON.stringify(detail),
  ]
}

/** 一次請求失敗的那一格：一句人話 + 技術細節。`lead` 是這一頁自己說「什麼沒做成」的前半句。 */
export function RequestFailed({ error, lead }: { error: unknown; lead?: string }) {
  const { t } = useTranslation()
  const text = t(PROBLEM_TEXT[requestProblem(error)])

  return (
    <div className="grid gap-1" data-testid="request-failed">
      <Notice signal="blocked" label={t('common.failed')}>
        {lead ? `${lead} ${text}` : text}
      </Notice>
      <TechnicalDetails lines={technicalOf(error)} />
    </div>
  )
}

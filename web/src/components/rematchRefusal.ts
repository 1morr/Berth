import type { TFunction } from 'i18next'

import { parseRematchRefusal } from '../api/files'
import { problemText } from './requestProblem'

/**
 * 擋下來時那一句：理由翻譯，`detail`（檔名、路徑或系統原文）原文接在後面。解析不出理由時照請求為什麼
 * 沒成說（M4 票 89）。不放在 `api/files.ts`：`api/` 不 import 畫面這一層。
 */
export function rematchRefusalText(t: TFunction, error: unknown): string {
  const said = parseRematchRefusal(error)
  if (!said) return problemText(t, error, t('request.notDone'))
  return [t(`rematch.refusal.${said.reason}`), said.detail].filter(Boolean).join(' ')
}

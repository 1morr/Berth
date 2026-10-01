import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { healthQueryOptions } from '../api/health'
import { GhostButton, Notice } from './controls'
import { PROBLEM_TEXT, requestProblem, SIGN_IN_PROBLEMS } from './requestProblem'
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

/**
 * 一次請求失敗的那一格：一句人話 + 技術細節。`lead` 是這一頁自己說「什麼沒做成」的前半句。
 * `ownerPending`：這一頁還以為沒有擁有者（精靈頁 1），401 因此是擁有者在別處成立了（`requestProblem`）。
 */
export function RequestFailed({
  error,
  lead,
  ownerPending = false,
}: {
  error: unknown
  lead?: string
  ownerPending?: boolean
}) {
  const { t } = useTranslation()
  const problem = requestProblem(error, { ownerPending })
  const text = t(PROBLEM_TEXT[problem])

  return (
    <div className="grid gap-1" data-testid="request-failed">
      <Notice signal="blocked" label={t('common.failed')}>
        {lead ? `${lead} ${text}` : text}
      </Notice>
      {SIGN_IN_PROBLEMS.has(problem) && <SignIn />}
      <TechnicalDetails lines={technicalOf(error)} />
    </div>
  )
}

/**
 * 去登入、登入之後回到這一頁。**先重問一次 `/health`**：路由守衛讀的是快取裡的那一份，擁有者在別處成立
 * 之前抓的那一份還說「沒有擁有者」，登入頁會把人送回精靈（`routes.tsx` 的 `loginRoute`）。
 */
function SignIn() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const here = useLocation({ select: (location) => location.href })

  async function signIn() {
    await queryClient.fetchQuery({ ...healthQueryOptions, staleTime: 0 }).catch(() => undefined)
    await navigate({ to: '/login', search: { redirect: here } })
  }

  return (
    <div>
      <GhostButton type="button" onClick={() => void signIn()}>
        {t('request.signIn')}
      </GhostButton>
    </div>
  )
}

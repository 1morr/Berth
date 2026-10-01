import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { signOut } from '../api/auth'

/**
 * 登出，回登入頁。頁首與精靈的「不是管理員」（M4 票 25：換一個管理員帳號登入）共用。
 *
 * `onSettled` 而不是 `onSuccess`：session 早就失效時後端照樣回 204，但網路斷了也該讓人離開這個身分。
 */
export function useSignOut() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: signOut,
    onSettled: async () => {
      // 登出後整份快取都不再屬於這個人。
      queryClient.clear()
      await navigate({ to: '/login' })
    },
  })
}

import { useState } from 'react'

import type { InterfaceLogin } from '../api/setup'

/**
 * 套件內 qBittorrent / Prowlarr 自己的介面登入（M4 票 07，`.scratch/m4/service-logins-shape.md`）。
 *
 * **設一組新登入就是建立**，所以密碼打兩次（票 06「密碼打兩次只在建立時」）；兩格都必填。
 * 泊位上還沒設過時欄位直接打開；設過之後說出帳號、按「更換」才打開，不帶就是登入照舊。
 */
export interface LoginDraft {
  username: string
  password: string
  confirm: string
}

export interface LoginProblems {
  username?: 'blank'
  password?: 'blank'
  confirm?: 'mismatch'
}

export function loginProblems(draft: LoginDraft): LoginProblems {
  return {
    ...(draft.username.trim() ? {} : { username: 'blank' }),
    ...(draft.password ? {} : { password: 'blank' }),
    ...(draft.password && draft.password !== draft.confirm ? { confirm: 'mismatch' } : {}),
  }
}

/** 送出時拿到的：要設的那一組、登入照舊（`null`），或欄位還有問題（`undefined`）。 */
export type TakenLogin = InterfaceLogin | null | undefined

export interface InterfaceLoginForm {
  draft: LoginDraft
  change: (patch: Partial<LoginDraft>) => void
  /** 按過送出之後才說哪一格不對，打字的當下不罵人。 */
  problems: LoginProblems
  /** 欄位打開著：還沒設過（必填），或按了「更換」。 */
  open: boolean
  openFields: () => void
  take: () => TakenLogin
  /** 設好之後清掉密碼、收起欄位；帳號留成剛設的那一個。 */
  reset: (username: string) => void
}

/**
 * @param current Berth 設下的帳號，空字串是還沒設過。
 * @param suggested 還沒設過時預填的帳號：擁有者的名字（shape 時使用者拍板）。
 * @param alwaysOpen 設定頁：那一區本來就是「更新登入」，沒有收起來的狀態。
 */
export function useInterfaceLogin({
  current,
  suggested,
  alwaysOpen = false,
}: {
  current: string
  suggested: string
  alwaysOpen?: boolean
}): InterfaceLoginForm {
  const [draft, setDraft] = useState<LoginDraft>({
    username: current || suggested,
    password: '',
    confirm: '',
  })
  const [changing, setChanging] = useState(false)
  const [checked, setChecked] = useState(false)
  const open = alwaysOpen || changing || !current

  return {
    draft,
    change: (patch) => setDraft((was) => ({ ...was, ...patch })),
    problems: checked ? loginProblems(draft) : {},
    open,
    openFields: () => setChanging(true),
    take: () => {
      if (!open) return null
      setChecked(true)
      if (Object.keys(loginProblems(draft)).length > 0) return undefined
      return { username: draft.username.trim(), password: draft.password }
    },
    reset: (username) => {
      setDraft({ username, password: '', confirm: '' })
      setChanging(false)
      setChecked(false)
    },
  }
}

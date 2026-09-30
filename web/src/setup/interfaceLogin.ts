import { useState } from 'react'

import type { InterfaceLogin } from '../api/setup'

/**
 * 套件內 qBittorrent / Prowlarr 自己的介面登入（M4 票 07，`.scratch/m4/service-logins-shape.md`）。
 *
 * **預設「沿用 Jellyfin 帳密」**（M4 票 15，brief §16.3）：帳號是擁有者、密碼打一次，後端先向 Jellyfin
 * 驗過才寫。取消勾選是票 07 的三格：設一組新登入就是建立，所以密碼打兩次；兩格都必填。
 * 頁上還沒設過時欄位直接打開；設過之後說出帳號、按「更換」才打開，不帶就是登入照舊。
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

/** `reuse`：沿用 Jellyfin 帳密時只看密碼那一格。 */
export function loginProblems(draft: LoginDraft, reuse = false): LoginProblems {
  if (reuse) return draft.password ? {} : { password: 'blank' }
  return {
    ...(draft.username.trim() ? {} : { username: 'blank' }),
    ...(draft.password ? {} : { password: 'blank' }),
    ...(draft.password && draft.password !== draft.confirm ? { confirm: 'mismatch' } : {}),
  }
}

/** 送出去的那一組。沿用時帳號留空：後端填成擁有者（`jellyfin.resolve_interface_login`）。 */
export function takenLogin(draft: LoginDraft, reuse: boolean): InterfaceLogin {
  return reuse
    ? { username: '', password: draft.password, reuse_owner: true }
    : { username: draft.username.trim(), password: draft.password, reuse_owner: false }
}

/** 送出時拿到的：要設的那一組、登入照舊（`null`），或欄位還有問題（`undefined`）。 */
export type TakenLogin = InterfaceLogin | null | undefined

export interface InterfaceLoginForm {
  draft: LoginDraft
  change: (patch: Partial<LoginDraft>) => void
  /** 沿用 Jellyfin 帳密。沒有擁有者可沿用時（不會發生在精靈裡）永遠是 `false`。 */
  reuse: boolean
  setReuse: (reuse: boolean) => void
  /** 擁有者的名字：沿用時的帳號。 */
  owner: string
  /** 按過送出之後才說哪一格不對，打字的當下不罵人。 */
  problems: LoginProblems
  /** 欄位打開著：還沒設過（必填），或按了「更換」。 */
  open: boolean
  openFields: () => void
  take: () => TakenLogin
  /** 設好之後清掉密碼、收起欄位；帳號留成剛設的那一個。 */
  reset: (username: string) => void
  /**
   * 改過幾次欄位（M4 票 21）。呼叫端在送出時記下它，之後拒絕與失敗只在它沒變時才畫——改了一格，
   * 上一次的「這不是 X 的 Jellyfin 密碼」說的就不是現在這幾格了。
   */
  edits: number
}

/**
 * @param current 那一台的帳號（Berth 設下的，或它自己就設過的），空字串是還沒設過。
 * @param owner 擁有者的名字：沿用時的帳號，取消勾選時預填它（票 07 shape 時使用者拍板）。
 * @param alwaysOpen 設定頁：那一區本來就是「更新登入」，沒有收起來的狀態。
 */
export function useInterfaceLogin({
  current,
  owner,
  alwaysOpen = false,
}: {
  current: string
  owner: string
  alwaysOpen?: boolean
}): InterfaceLoginForm {
  const [draft, setDraft] = useState<LoginDraft>({
    username: current || owner,
    password: '',
    confirm: '',
  })
  const [reuse, setReuse] = useState(Boolean(owner))
  const [changing, setChanging] = useState(false)
  const [checked, setChecked] = useState(false)
  const [edits, setEdits] = useState(0)
  const open = alwaysOpen || changing || !current
  const reusing = reuse && Boolean(owner)

  return {
    draft,
    change: (patch) => {
      setDraft((was) => ({ ...was, ...patch }))
      setEdits((count) => count + 1)
    },
    reuse: reusing,
    // 換一種登入：打過的密碼是另一種的（Jellyfin 的，或新的那一組），不帶過去；上一次按過送出的
    // 「哪一格不對」也不帶——確認欄還沒填就說「不一樣」是冤枉人（M4 票 21）。
    setReuse: (next) => {
      setReuse(next)
      setDraft((was) => ({ ...was, password: '', confirm: '' }))
      setChecked(false)
      setEdits((count) => count + 1)
    },
    owner,
    problems: checked ? loginProblems(draft, reusing) : {},
    open,
    openFields: () => setChanging(true),
    take: () => {
      if (!open) return null
      setChecked(true)
      if (Object.keys(loginProblems(draft, reusing)).length > 0) return undefined
      return takenLogin(draft, reusing)
    },
    reset: (username) => {
      // 沿用時送出去的帳號是空的（後端填成擁有者），留下來的是擁有者的名字。
      setDraft({ username: username || owner, password: '', confirm: '' })
      setChanging(false)
      setChecked(false)
    },
    edits,
  }
}

import { useEffect, useEffectEvent, useRef, useState } from 'react'

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

/** 哪一個服務的介面：文案說得出是誰的登入、打開哪個網址，也決定照哪一份規則擋。 */
export type LoginService = 'qbittorrent' | 'prowlarr'

/** 那個服務自己收什麼樣的帳密。沒有規則的服務（Prowlarr）只要兩格都填。 */
export interface LoginRules {
  usernameMin: number
  passwordMin: number
  /** 帳號不能有冒號。 */
  noColon: boolean
}

/**
 * qBittorrent 5.2.0 起 `setPreferences` 照這三條拒收，帳號還先寫進去（brief §20.2，M4 票 26 實測）。
 * 4.4–5.1 自己的設定頁也要求同樣的長度，所以不分版本照它擋。字數是 `String.length`（UTF-16 code
 * unit），與 qBittorrent 的 QString 同一種算法。
 */
export const LOGIN_RULES = {
  qbittorrent: { usernameMin: 3, passwordMin: 6, noColon: true },
  prowlarr: null,
} as const satisfies Record<LoginService, LoginRules | null>

export interface LoginProblems {
  /** 沿用時是擁有者的名字不合規則（那一格不在畫面上，說在密碼那一格）。 */
  username?: 'blank' | 'short' | 'colon'
  password?: 'blank' | 'short'
  confirm?: 'mismatch'
}

/**
 * `reuse`：沿用 Jellyfin 帳密時只看密碼那一格，再加上擁有者的名字（`owner`）合不合規則——它就是要寫進去的帳號。
 */
export function loginProblems(
  draft: LoginDraft,
  {
    reuse = false,
    rules = null,
    owner = '',
  }: { reuse?: boolean; rules?: LoginRules | null; owner?: string } = {},
): LoginProblems {
  const username = reuse ? owner : draft.username.trim()
  const usernameProblem = !username
    ? 'blank'
    : rules && username.length < rules.usernameMin
      ? 'short'
      : rules?.noColon && username.includes(':')
        ? 'colon'
        : undefined
  const passwordProblem = !draft.password
    ? 'blank'
    : rules && draft.password.length < rules.passwordMin
      ? 'short'
      : undefined
  if (reuse) {
    return {
      ...(usernameProblem && usernameProblem !== 'blank' ? { username: usernameProblem } : {}),
      ...(passwordProblem ? { password: passwordProblem } : {}),
    }
  }
  return {
    ...(usernameProblem ? { username: usernameProblem } : {}),
    ...(passwordProblem ? { password: passwordProblem } : {}),
    ...(draft.password && draft.password !== draft.confirm ? { confirm: 'mismatch' } : {}),
  }
}

/** 送出去的那一組。沿用時帳號留空：後端填成擁有者（`jellyfin.resolve_interface_login`）。 */
export function takenLogin(draft: LoginDraft, reuse: boolean): InterfaceLogin {
  return reuse
    ? { username: '', password: draft.password, reuse_owner: true }
    : { username: draft.username.trim(), password: draft.password, reuse_owner: false }
}

/**
 * 頁 1 帶過來的那一組（M4 票 40，brief §19 D4）照這個服務的規則合不合：不合就說哪裡不合（帳號與密碼
 * 的問題各一個），合（或根本沒帶）就是 `null`。沿用時帳號是擁有者，所以兩個都要看。
 */
export function carriedUnfit(
  service: LoginService,
  carriedPassword: string | null,
  owner: string,
): LoginProblems | null {
  if (carriedPassword === null) return null
  const problems = loginProblems(reuseDraft(carriedPassword), {
    reuse: true,
    rules: LOGIN_RULES[service],
    owner,
  })
  return Object.keys(problems).length > 0 ? problems : null
}

/** 沿用時的欄位：只有密碼那一格（帳號是擁有者，後端填）。 */
function reuseDraft(password: string): LoginDraft {
  return { username: '', password, confirm: '' }
}

/**
 * 頁 1 勾了「也用這組」時，套件內的那一台還沒有介面登入就自動送一次沿用 Jellyfin 帳密（M4 票 40）。
 * 照舊經 `reuse_owner`：後端先向 Jellyfin 驗過才寫。**只送一次**，不管結果——失敗了欄位照常打開，
 * 拒絕與失敗由呼叫端照手動送出的那一套說。
 *
 * @param carriedPassword 合規則的那一組（`carriedUnfit` 不是 `null` 的不傳），沒有就是 `null`。
 * @param needed 那一台還沒有介面登入，頁上本來就要問。
 */
export function useCarriedLogin({
  carriedPassword,
  needed,
  apply,
}: {
  carriedPassword: string | null
  needed: boolean
  apply: (login: InterfaceLogin) => Promise<unknown>
}): { applying: boolean } {
  const [applying, setApplying] = useState(false)
  const sent = useRef(false)
  // 送出的那一刻用最新的 `apply`：它讀呼叫端當下的欄位版本。
  const send = useEffectEvent((password: string) => {
    setApplying(true)
    const done = () => setApplying(false)
    apply(takenLogin(reuseDraft(password), true)).then(done, done)
  })
  useEffect(() => {
    if (carriedPassword === null || !needed || sent.current) return
    sent.current = true
    send(carriedPassword)
  }, [carriedPassword, needed])
  return { applying }
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
  /** 照哪一份規則擋（`LOGIN_RULES`）。文案要說出那個數字。 */
  rules: LoginRules | null
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
 * @param service 哪一個服務的登入：照它的規則擋（`LOGIN_RULES`）。
 * @param current 那一台的帳號（Berth 設下的，或它自己就設過的），空字串是還沒設過。
 * @param owner 擁有者的名字：沿用時的帳號，取消勾選時預填它（票 07 shape 時使用者拍板）。
 * @param alwaysOpen 設定頁：那一區本來就是「更新登入」，沒有收起來的狀態。
 * @param reuse 一開始勾不勾沿用（預設勾）。
 */
export function useInterfaceLogin({
  service,
  current,
  owner,
  alwaysOpen = false,
  reuse: reuseAtFirst = true,
}: {
  service: LoginService
  current: string
  owner: string
  alwaysOpen?: boolean
  /** 一開始勾不勾沿用：頁 1 那一組不合這個服務的規則時（`carriedUnfit`）一開始就是自設的三格。 */
  reuse?: boolean
}): InterfaceLoginForm {
  const [draft, setDraft] = useState<LoginDraft>({
    username: current || owner,
    password: '',
    confirm: '',
  })
  const [reuse, setReuse] = useState(reuseAtFirst && Boolean(owner))
  const [changing, setChanging] = useState(false)
  const [checked, setChecked] = useState(false)
  const [edits, setEdits] = useState(0)
  const open = alwaysOpen || changing || !current
  const reusing = reuse && Boolean(owner)
  const rules = LOGIN_RULES[service]
  const problemsNow = () => loginProblems(draft, { reuse: reusing, rules, owner })

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
    problems: checked ? problemsNow() : {},
    rules,
    open,
    openFields: () => setChanging(true),
    take: () => {
      if (!open) return null
      setChecked(true)
      if (Object.keys(problemsNow()).length > 0) return undefined
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

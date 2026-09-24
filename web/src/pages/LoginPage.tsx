import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions, SIGN_IN_KEY, signIn, type Credentials, type Me } from '../api/auth'
import { ApiError } from '../api/client'
import { destination } from '../auth/destination'
import { CopyLine, Field, Notice, PasswordField, PrimaryButton } from '../components/controls'
import { LanguageToggle } from '../components/LanguageToggle'

/**
 * 登入頁。方向見 `.scratch/m0/login-shape.md`：單一登船口窗格，不畫泊位板——
 * 泊位板講的是精靈那四個泊位，登入時一個都還沒開始。
 */
export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { redirect, expired } = useSearch({ from: '/login' })
  const [credentials, setCredentials] = useState<Credentials>({ username: '', password: '' })
  const password = useRef<HTMLInputElement>(null)

  const login = useMutation({
    mutationKey: SIGN_IN_KEY,
    mutationFn: signIn,
    onSuccess: (me: Me) => {
      queryClient.setQueryData(meQueryOptions.queryKey, me)
      void navigate({ href: destination(redirect) })
    },
    // 被拒絕之後焦點回到密碼欄：帳號多半是對的，要改的是下面那一格。
    onError: () => password.current?.focus(),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    login.mutate(credentials)
  }

  const failure = login.error ? explain(login.error) : null

  return (
    <div className="flex min-h-dvh flex-col bg-hull text-ink">
      <header className="flex items-center gap-x-6 border-b-2 border-rule-strong px-6 py-4">
        <p className="value text-lg font-semibold tracking-tight">{t('app.name')}</p>
        <span className="ml-auto">
          <LanguageToggle />
        </span>
      </header>

      <main className="flex flex-1 justify-center px-6 py-10">
        {/* `my-auto` 而不是 `items-center`：矮螢幕（手機橫放、開了鍵盤）上 flex 置中會把
            上緣切掉而且捲不回去，margin 置中則退化成一般間距。 */}
        <div className="my-auto w-full max-w-[26rem]">
          <section className="border-2 border-rule bg-well" aria-labelledby="login-heading">
            <h1 className="flex items-center gap-3 border-b-2 border-rule bg-deck px-4 py-3">
              <span className="label bg-hull px-2 py-1.5 text-ink">{t('login.code')}</span>
              <span id="login-heading" className="label text-ink-dim">
                {t('login.title')}
              </span>
            </h1>

            <form className="grid gap-4 px-4 py-5" onSubmit={submit} aria-busy={login.isPending}>
              {expired === true && !failure && (
                <Notice signal="assigned" label={t('login.expiredChip')}>
                  {t('login.expired')}
                </Notice>
              )}

              {failure && (
                <Notice signal="blocked" label={t('common.failed')}>
                  {t(failure.message, failure.values)}
                </Notice>
              )}
              {failure?.command && <CopyLine command={failure.command} />}

              <Field
                label={t('login.field.username')}
                value={credentials.username}
                autoComplete="username"
                autoFocus
                disabled={login.isPending}
                onChange={(event) =>
                  setCredentials((was) => ({ ...was, username: event.target.value }))
                }
              />
              <PasswordField
                ref={password}
                label={t('login.field.password')}
                value={credentials.password}
                autoComplete="current-password"
                disabled={login.isPending}
                onChange={(event) =>
                  setCredentials((was) => ({ ...was, password: event.target.value }))
                }
              />

              <PrimaryButton type="submit" busy={login.isPending}>
                {login.isPending ? t('login.submitting') : t('login.submit')}
              </PrimaryButton>
            </form>
          </section>

          {/* Berth 沒有自己的密碼——這句話一次解釋了帳密從哪裡來、為什麼沒有註冊，
              以及為什麼 Jellyfin 掛掉時誰都進不來（brief §11）。 */}
          <p className="mt-4 text-xs text-ink-dim">{t('login.source')}</p>
        </div>
      </main>
    </div>
  )
}

interface Failure {
  message: 'login.error.refused' | 'login.error.unavailable' | 'login.error.unexpected'
  values?: { status: number }
  /** 可複製的下一步。失敗要說得出下一步（PRODUCT.md 原則 4）。 */
  command?: string
}

/**
 * 三種失敗要說三句不同的話。全部歸到「帳號或密碼不對」的話，一個被前置代理擋掉的請求
 * 會讓使用者一直重打其實正確的密碼。
 */
function explain(error: Error): Failure {
  const status = error instanceof ApiError ? error.status : 0
  if (status === 401) return { message: 'login.error.refused' }
  if (status === 503) {
    return { message: 'login.error.unavailable', command: 'docker compose ps jellyfin' }
  }
  return {
    message: 'login.error.unexpected',
    values: { status },
    command: 'docker compose logs --tail 50 berth',
  }
}

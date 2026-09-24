import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MIN_QUERY_LENGTH, searchQueryOptions, type DiscoverItem } from '../api/discover'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { CONFIRM_ACTIONS, Field, GhostButton, PrimaryButton } from '../components/controls'
import { SEARCH_DEBOUNCE_MS, useDebounced } from '../components/useDebounced'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { displayRound } from '../i18n/displayRound'

/**
 * 認領類的兩顆（重新入庫、認領 torrent）按下去先選作品（M2 票 10，2026-09-23 使用者拍板）。
 *
 * **就地展開，不是 dialog**（The Failure Expands In Place Rule，同 `ConfirmAction`）：按鈕換成一個
 * 搜尋欄，選一部之後主動作說出「入庫到《X》」再按一次。搜的是探索頁同一支 `/discover/search`，
 * 所以結果與使用者平常找作品看到的是同一份，防抖也是同一個。沒選作品時主動作不畫：後端也會拒絕
 * （`media_required`），但按下去才被拒的按鈕不該畫出來。
 *
 * 搜尋框預填後端從名字讀出的標題（`issue.query`，照 Sonarr / Radarr Manual Import），展開時
 * 焦點進搜尋框：要做的第一件事是核對或改那個字。
 */
export function WorkPicker({
  label,
  initialQuery,
  pending,
  pendingLabel,
  onPick,
}: {
  label: string
  initialQuery: string
  pending: boolean
  pendingLabel: string
  onPick: (mediaId: string) => void
}) {
  const { t, i18n } = useTranslation()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const [query, setQuery] = useState(initialQuery)
  const [picked, setPicked] = useState<DiscoverItem | null>(null)
  const search = useRef<HTMLInputElement>(null)
  const headingId = useId()
  const debounced = useDebounced(query.trim(), SEARCH_DEBOUNCE_MS)
  const found = useQuery({
    ...searchQueryOptions(debounced),
    enabled: asked && debounced.length >= MIN_QUERY_LENGTH,
  })

  // 排在 `useInPlaceConfirm` 之後：它先把焦點給整個確認區塊，這裡再送進搜尋框。
  useEffect(() => {
    if (asked) search.current?.focus()
  }, [asked])

  if (!asked) {
    return (
      <GhostButton ref={trigger} type="button" busy={pending} onClick={open}>
        {pending ? pendingLabel : label}
      </GhostButton>
    )
  }

  const titleOf = (item: DiscoverItem) =>
    displayRound(i18n.language, { 'zh-Hant': item.title, en: item.title_en }) || item.title_en
  const items = found.data?.items ?? []

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={headingId}>
      <p id={headingId} className="label text-ink-dim">
        {t('issues.pick.label')}
      </p>
      <Field
        ref={search}
        label={t('issues.pick.placeholder')}
        type="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setPicked(null)
        }}
      />
      {found.isFetching && <p className="text-xs text-ink-dim">{t('issues.pick.searching')}</p>}
      {found.data?.problem ? (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {t('issues.pick.off')}
        </p>
      ) : found.data && items.length === 0 ? (
        <p className="text-xs text-ink-dim">{t('issues.pick.none')}</p>
      ) : null}
      {items.length > 0 && (
        <ul className="grid gap-1" aria-label={t('issues.pick.label')}>
          {items.slice(0, 8).map((item) => (
            <li key={item.id}>
              <button
                type="button"
                aria-pressed={picked?.id === item.id}
                onClick={() => setPicked(item)}
                className={`value flex w-full flex-wrap items-baseline gap-x-2 border-2 px-3 py-2 text-left text-sm text-ink ${
                  picked?.id === item.id
                    ? 'border-rule-strong bg-deck'
                    : 'border-rule hover:border-rule-strong'
                }`}
              >
                <span className="wrap-anywhere">{titleOf(item)}</span>
                <span className="text-xs text-ink-dim">
                  {[item.year, t(`issues.pick.${item.kind}`)].filter(Boolean).join(' · ')}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className={CONFIRM_ACTIONS}>
        {picked ? (
          <PrimaryButton
            type="button"
            busy={pending}
            onClick={() => {
              close()
              onPick(picked.id)
            }}
          >
            {pending ? pendingLabel : t('issues.pick.confirm', { title: titleOf(picked) })}
          </PrimaryButton>
        ) : (
          <span />
        )}
        <GhostButton type="button" onClick={close}>
          {t('issues.pick.cancel')}
        </GhostButton>
      </div>
    </ConfirmPanel>
  )
}

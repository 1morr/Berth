import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import {
  MIN_QUERY_LENGTH,
  popularQueryOptions,
  searchQueryOptions,
  trendingQueryOptions,
} from '../api/discover'
import { Field } from '../components/controls'
import { MediaWall } from '../discover/MediaWall'
import tmdbLogo from '../assets/tmdb.svg'

/** 鍵入即搜的防抖（使用者拍板）。每一個不同的字串都會花掉使用者自備的 TMDB 額度。 */
const DEBOUNCE_MS = 500

/**
 * 探索頁 `/`（票 03、`.scratch/m1/discover-shape.md`）。
 *
 * 這是精靈跑完、登入之後看到的第一個畫面，而它是**找東西的地方**，不是「看它有沒有壞」的地方
 * ——健康頁留在導覽列上。整頁只有一個工作：辨認出一部作品。
 *
 * 搜尋有結果時**接管整面牆**，趨勢與熱門收起來；清空搜尋框就回來。一屏只有一面牆，
 * 手機上才不必捲過兩百格才看得到搜尋結果。
 */
export function DiscoverPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query.trim(), DEBOUNCE_MS)
  const searching = debounced.length >= MIN_QUERY_LENGTH

  const trending = useQuery(trendingQueryOptions)
  const popular = useQuery(popularQueryOptions)
  const results = useQuery(searchQueryOptions(debounced))

  const retry = () => void queryClient.invalidateQueries({ queryKey: ['discover'] })

  return (
    <div className="mx-auto grid w-full max-w-[110rem] gap-8 px-6 py-8">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div className="min-w-0 flex-1 sm:max-w-[28rem]">
          <Field
            label={t('discover.search.label')}
            type="search"
            value={query}
            placeholder={t('discover.search.placeholder')}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        {/* 牆換掉了要說得出來——螢幕閱讀器使用者看不到格子從 40 格變成 2 格。 */}
        <p aria-live="polite" className="text-sm text-ink-dim">
          {searchStatus()}
        </p>
      </div>

      {searching ? (
        <MediaWall
          title={t('discover.results', { query: debounced })}
          result={results.data}
          pending={results.isPending || results.isFetching}
          empty={t('discover.search.none', { query: debounced })}
          onRetry={retry}
        />
      ) : (
        <>
          <MediaWall
            title={t('discover.trending')}
            result={trending.data}
            pending={trending.isPending}
            empty={t('discover.empty')}
            onRetry={retry}
          />
          <MediaWall
            title={t('discover.popular')}
            result={popular.data}
            pending={popular.isPending}
            empty={t('discover.empty')}
            onRetry={retry}
          />
        </>
      )}

      {/* TMDB 的條款要求顯示標誌與這一句（brief §20.3）。它是法定聲明，不是頁尾裝飾。 */}
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t-2 border-rule pt-4">
        <img src={tmdbLogo} alt="TMDB" height={16} className="h-4 w-auto" />
        <p className="max-w-prose text-xs text-ink-dim">{t('discover.attribution')}</p>
      </footer>
    </div>
  )

  function searchStatus() {
    if (query.trim().length > 0 && query.trim().length < MIN_QUERY_LENGTH) {
      return t('discover.search.tooShort', { count: MIN_QUERY_LENGTH })
    }
    if (!searching) return ''
    if (results.isFetching) return t('discover.search.searching')
    if (results.data?.problem) return ''
    return t('discover.search.count', { count: results.data?.items.length ?? 0 })
  }
}

/** 鍵入即搜，但不是每個按鍵都送一次。 */
function useDebounced(value: string, delay: number) {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return settled
}

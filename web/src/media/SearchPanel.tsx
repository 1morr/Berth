import { useId, useImperativeHandle, useRef, useState, type ReactNode, type Ref } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import {
  choiceOf,
  queriesQueryOptions,
  rememberNames,
  searchTorrents,
  type Batch,
  type MissingScope,
  type NameChip,
  type NameKind,
  type QueryChoice,
  type QueryPlan,
} from '../api/search'
import { COMPACT_BUTTON, PrimaryButton } from '../components/controls'
import { seasonCode } from '../components/episodes'
import { RequestFailed } from '../components/RequestFailed'
import type { SetupStep } from '../api/schemas'
import { ExpandHint } from '../components/ExpandHint'
import { SectionHeading } from '../components/SectionHeading'
import { StepLine } from '../components/StepLine'
import { IndexerNotice } from './IndexerNotice'
import { FilteredResults } from './FilteredResults'
import { QueryChoices } from './QueryChoices'
import { RoutePicker } from './RoutePicker'
import { listedTotal } from './searchFilter'
import type { SortKey } from './searchResult'

export interface SearchHandle {
  /** 從季表的缺集開始搜：`season` 是 `null` 時整部作品（M1.5 票 10）。 */
  searchMissing: (season: number | null) => void
}

/**
 * 搜尋 torrent 與結果表（`.scratch/m1/search-results-shape.md`，票 08）。
 *
 * Media 詳情頁區塊序列的第 3 塊，往季集與檔案清單之間插進來，不重排前面兩區。
 *
 * **待命，按了才搜**（使用者 2026-09-10 拍板）：一次搜尋實測 35–85 秒，因為 Prowlarr 收到
 * 請求之後要現場去連它認得的每一個追蹤站。進頁面就自動搜等於替每個只想看季集表的人
 * 對五個公開站發五輪查詢。所以它是 mutation 不是 query——使用者按下去才發生的事。
 *
 * 按下之前畫面先列出**會送出去的那幾個關鍵字**（PRODUCT 原則 2：動手前先給看）。那份清單
 * 由後端算（`GET /api/search/queries`），不是前端重算一份——它要看快照的標題集合與季數，
 * 兩邊各算一次遲早會給出不同的答案。
 *
 * Route 下拉住在這一區，但**搜尋不看它**（票 14e）：它只決定結果表裡那一顆送單送去哪裡。
 * **資料夾名也住在這一區**（M1.5 票 08，原本在身分帶的剖面裡）：它是送單那一刻會寫死的那一串字。
 *
 * 搜尋中逐條亮起的纜繩是署名互動；**結束之後有回應的收成一行**，失敗的照舊一條一條畫在上面（M1.5 票 08：
 * 全綠的纜繩曾把結果表推到下一屏，票 15 critique 量到 311px）。
 *
 * 季表上的缺集也從這裡搜（M1.5 票 10）：那兩顆按鈕呼叫 `SearchHandle.searchMissing`，結果照舊畫在這一區塊，
 * 照舊送單。**查詢仍然由後端產生**——換成缺的那幾集之後，預覽與真的送出去的那幾個還是同一份。
 *
 * 缺的季放不下一批時**分批問**（M3 票 20）：一批問完，`BatchLine` 說這一批問了哪幾季、下一批是哪幾季，
 * 「問下一批」由人按——結果要人挑，背景自己問完也沒有人看。
 *
 * **問哪些名字、哪幾季由人開關**（M4 票 84，`.scratch/m4/search-choose-shape.md`）：`QueryChoices` 的 chip。
 * 還沒動過時（`choice` 是 `null`）照後端的預設畫；動過之後預覽、搜尋、搜缺的集都帶同一份選擇。名字的種類
 * 按下去當下就記住（`PUT /api/search/names`），下一部作品打開時照它開；別名與季不記。
 */
export function SearchPanel({ media, ref }: { media: Media; ref: Ref<SearchHandle> }) {
  const { t } = useTranslation()
  const headingId = useId()
  const keywordId = useId()
  const heading = useRef<HTMLHeadingElement>(null)

  // `undefined` 是「這一輪還沒動過」，與刻意選「尚未指定」（`null`）不是同一件事。
  const [route, setRoute] = useState<number | null | undefined>(undefined)
  const chosen = route === undefined ? preselected(media) : route
  const [keyword, setKeyword] = useState('')
  const [sort, setSort] = useState<SortKey>('seeders')
  // `null` = 照作品名搜（預設）。有值時這一區塊搜的是季表上缺的那幾集。
  const [missing, setMissing] = useState<MissingScope | null>(null)
  // `null` = 還沒動過 chip：後端照記住的名字種類與預設的季算（M4 票 84）。
  const [choice, setChoice] = useState<QueryChoice | null>(null)

  // 換一個選擇時舊的預覽先留著（`keepPreviousData`）：chip 一按整塊就閃成「—」的話，人看不出按了什麼。
  const planned = useQuery({
    ...queriesQueryOptions(media.id, missing, choice),
    placeholderData: keepPreviousData,
  })
  const queryClient = useQueryClient()
  // 記住之後別部作品的預覽（還在快取裡的那幾份）就過時了：照新的種類重算。
  const remember = useMutation({
    mutationFn: rememberNames,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['search', 'queries'] }),
  })
  // 關鍵字、範圍與開了的 chip 都當**參數**傳，不從 render 的 closure 讀：季表那兩顆按鈕在同一個 tick 裡清掉關鍵字
  // 又送出搜尋，而「清掉」要等下一次 render 才生效——讀 closure 的話送出去的會是上一個關鍵字，
  // 而 `q` 有值時後端只問那一個（票 08），畫面上的預覽就成了謊話。
  const search = useMutation({
    mutationFn: ({
      q,
      scope,
      picked,
    }: {
      q: string
      scope: MissingScope | null
      picked: QueryChoice | null
    }) => searchTorrents({ media: media.id, q, missing: scope, choice: picked }),
  })

  // 季表那兩顆按鈕**直接**做這件事（React 的「觸發子元件的動作」逃生口），不繞一圈狀態再用
  // effect 追：狀態鏡射會讓「按第二次」與「按下之後又改了關鍵字」變成兩個要對齊的真相。
  useImperativeHandle(ref, () => ({
    searchMissing(season) {
      setKeyword('')
      const scope = { season, fromSeason: 0 }
      setMissing(scope)
      search.mutate({ q: '', scope, picked: choice })
      // 結果畫在這一區塊裡，所以焦點也要到這裡來——季表在下面好幾屏（shape §4）。
      // 瀏覽器會把拿到焦點的元素捲進畫面，所以不必自己捲一次。
      heading.current?.focus()
    },
  }))

  const results = search.data
  const listed = results ? listedTotal(results) : 0
  const problem = results ? results.problem : planned.data?.problem
  const typed = keyword.trim()
  const refusal = planned.data && !typed ? refusalOf(planned.data, choice, missing) : null
  const refusalId = useId()
  // 送出去的選擇要是畫面上那一份預覽算的那一份：預覽還在換（`isPlaceholderData`）時搜尋鍵停著，
  // 不然按下去送的是新的選擇、畫面列的卻是舊的查詢（code-review）。
  const settling = !typed && planned.isPlaceholderData

  return (
    <section className="grid gap-4" aria-labelledby={headingId}>
      <SectionHeading
        id={headingId}
        label={t('search.title')}
        headingRef={heading}
        extra={
          // 只說總數：送來的比總數少時，表格裡那一組底下說只列了幾筆（M4 票 83），標頭不再說第二次。
          listed > 0 && (
            <p className="value text-xs text-ink-dim">{t('search.count', { count: listed })}</p>
          )
        }
      />

      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (refusal || settling) return
          search.mutate({ q: typed, scope: missing, picked: choice })
        }}
      >
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,16rem)_auto] lg:items-end">
          <p className="grid gap-2">
            <label htmlFor={keywordId} className="label text-ink-dim">
              {t('search.keyword')}
            </label>
            <input
              id={keywordId}
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              // 從季表按進來之後留空問的是缺的集（票 13）：照舊說「作品的各個名字」就與底下的預覽相反。
              placeholder={
                missing === null
                  ? t('search.keywordPlaceholder')
                  : t('search.keywordPlaceholderMissing')
              }
              className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink placeholder:text-ink-dim focus:border-ink"
            />
          </p>
          <RoutePicker media={media} value={chosen} onChange={setRoute} />
          {/* 問著的時候只換文字、按了不再問一次（M3 票 06：一輪 35–85 秒、打的是公開站，重按就是整輪查詢再打一次）。
              **組出來的查詢超過上限、或一個名字都沒開時停用**（M4 票 84 推翻票 02b 的「按鈕永遠按得下去」，
              票面明訂）：原因就在旁邊那一行，掛成按鈕的描述。 */}
          <span className="lg:w-40">
            <PrimaryButton
              type="submit"
              busy={search.isPending}
              disabled={refusal !== null || settling}
              aria-describedby={refusal ? refusalId : undefined}
            >
              {search.isPending ? t('search.submitting') : t('search.submit')}
            </PrimaryButton>
          </span>
        </div>

        {/* 快照還沒讀到時沒有名字可選：不畫一排空的 chip（shape〈狀態與範圍〉）。 */}
        {planned.data && planned.data.names.length > 0 && (
          <QueryChoices
            plan={planned.data}
            choice={choice ?? choiceOf(planned.data)}
            seasons={missing === null}
            onChange={setChoice}
            onName={(chip, on) => rememberKinds(chip, on, remember.mutate)}
          />
        )}

        <QueryPreview
          keyword={keyword}
          planned={planned.data?.queries}
          batch={planned.data?.batch ?? null}
          missing={missing}
          onTitles={() => setMissing(null)}
        >
          <QueryCost
            count={typed ? 1 : (planned.data?.queries.length ?? 0)}
            limit={planned.data?.limit ?? 0}
            refusal={refusal}
            refusalId={refusalId}
          />
        </QueryPreview>
      </form>

      <FolderLine media={media} />

      {search.isError && <RequestFailed error={search.error} lead={t('search.failed')} />}

      {/* 一次搜尋要 35–85 秒。那段時間裡畫面上要有東西在動，而這塊板子沒有 spinner——
          動的是纜繩：先鋪出要問的那幾個關鍵字（`working`），一有結果就換成筆數
          （shape brief §3 的焦點時刻，與精靈的靠泊序列是同一種東西）。 */}
      {search.isPending ? (
        <ol className="grid gap-2">
          {pending(keyword, planned.data?.queries).map((attempt) => (
            <StepLine
              key={attempt.step}
              label={attempt.step}
              service={t('search.indexers')}
              summary={attempt.detail}
              row={attempt}
            />
          ))}
        </ol>
      ) : (
        results && results.attempts.length > 0 && <Cables attempts={results.attempts} />
      )}

      {/* 沒接索引站在按下去之前就說（票 13，`/search/queries` 先帶 `problem`）：不然畫面一直說「會拿這幾個
          名字去問」，按下去才知道根本沒有地方可問。搜過之後以那一次的結果為準，同一件事只說一次。 */}
      {problem && <IndexerNotice problem={problem} detail={results?.detail ?? ''} />}

      {results?.batch && isBatched(results.batch, missing) && missing && (
        <BatchLine
          key={missing.fromSeason}
          batch={results.batch}
          onNext={(fromSeason) => {
            const scope = { ...missing, fromSeason }
            setMissing(scope)
            search.mutate({ q: '', scope, picked: choice })
          }}
        />
      )}

      {results && !results.problem && (
        <FilteredResults
          key={search.submittedAt}
          results={results}
          typed={search.variables?.q ?? ''}
          media={media}
          route={chosen}
          sort={sort}
          onSort={setSort}
        />
      )}

      {/* 整頁只有這一區塊的內容會變，看不見畫面的人得知道按下去發生了什麼。 */}
      <p aria-live="polite" className="sr-only">
        {results ? t('search.announce', { count: listed, failed: failedCount(results) }) : ''}
      </p>
    </section>
  )
}

/**
 * 按下去之前先給看：Berth 會拿哪幾個查詢去問，以及這要花多少、多久。
 *
 * 它是一個欄位（M4 票 84b）：標籤與關鍵字、名字、資料夾名同一種，查詢數寫在標籤裡。沒有季的時候清單與開著的
 * 名字 chip 是同一組字，所以不再另起一句「Berth 會問這幾個」；清單照留——開了季之後它與 chip 不同。
 *
 * 自己打了關鍵字時就只問那一個——他比 TMDB 更知道自己在找什麼，所以清單換成那一句、標籤說 1 個。
 *
 * 從季表按進來時（`missing`）問的是缺的那幾集，而那幾個關鍵字**也是後端給的**（票 10）：清單本身看不出
 * 問的是缺的集，所以標籤底下照實說範圍，旁邊留一條回作品名的路——按進來之後沒有出口的話，只剩重整這一招。
 * 打了關鍵字時那一句不說（問的是打的那一個，不是缺的集），出口照留：清掉關鍵字之後問的又是缺的集。
 */
function QueryPreview({
  keyword,
  planned,
  batch,
  missing,
  onTitles,
  children,
}: {
  keyword: string
  planned: string[] | undefined
  batch: Batch | null
  missing: MissingScope | null
  onTitles: () => void
  /** 代價與等待那一句（`QueryCost`）：緊接在查詢底下，與它說的是同一份清單。 */
  children: ReactNode
}) {
  const { t } = useTranslation()
  const typed = keyword.trim()
  const asked = typed ? [typed] : (planned ?? [])

  return (
    <div className="grid gap-2">
      {/* 數字照 The Tabular Rule：標籤在 zh-Hant 是無襯線，等寬數字要另外開。 */}
      <p className="label text-ink-dim tabular-nums">
        {t('search.willAskCount', { count: asked.length })}
      </p>
      <div className="grid gap-1">
        {missing !== null && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {!typed && (
              <span className="max-w-prose text-xs text-ink-dim">
                {missing.season === null
                  ? t('search.willAskMissing')
                  : t('search.willAskMissingSeason', { season: seasonCode(missing.season) })}
              </span>
            )}
            <button type="button" onClick={onTitles} className={COMPACT_BUTTON}>
              {t('search.missingOff')}
            </button>
          </p>
        )}
        {!typed && batch && isBatched(batch, missing) && (
          <p className="max-w-prose text-xs text-ink-dim">
            {t('search.batch.preview', { seasons: seasonList(t, batch.seasons) })}
            {batch.later > 0 ? t('search.batch.laterPreview', { later: batch.later }) : ''}
          </p>
        )}
        {/* 關鍵字是機器字串（送出去的就是它），走 `.value`。一個查詢一項（M4 票 84）：開了中文名與季之後一行放不下，
            串成一段字的話「大熊餐廳 第5季」會從中間斷開，看不出那是一個查詢。 */}
        {asked.length > 0 ? (
          <ul
            aria-label={t('search.queriesList')}
            className="value flex max-w-prose flex-wrap gap-x-4 gap-y-1 text-xs text-ink"
          >
            {asked.map((query) => (
              <li key={query} className="wrap-anywhere">
                {query}
              </li>
            ))}
          </ul>
        ) : (
          <p className="value text-xs text-ink">—</p>
        )}
        {children}
      </div>
    </div>
  )
}

/**
 * 為什麼現在不能按搜尋（M4 票 84）：一個名字都沒開，或組出來的查詢超過上限。打了關鍵字時不看它。
 * 搜缺的集時沒有季 chip，超過上限只能關名字（開了一大堆拉丁字別名時，整季缺的一季就超過）。
 * 這部作品一個名字都沒有（快照還沒讀到）不算：按下去照舊由後端說 `no_query`。
 */
type Refusal = 'noName' | 'tooMany' | 'tooManyNames'

function refusalOf(
  plan: QueryPlan,
  choice: QueryChoice | null,
  missing: MissingScope | null,
): Refusal | null {
  if (plan.names.length > 0 && (choice ?? choiceOf(plan)).names.length === 0) return 'noName'
  if (plan.queries.length <= plan.limit) return null
  return missing === null ? 'tooMany' : 'tooManyNames'
}

/**
 * 按下去之前說出代價（M4 票 84）：要問幾個查詢——一個查詢就是請索引站背後的每一個站現場搜一次——與要等
 * 多久，併成一句（票 84b）。不能按的時候整句換成原因，掛在搜尋鍵
 * 的描述上，等多久那半句不說。一個查詢都沒有時不畫。
 */
function QueryCost({
  count,
  limit,
  refusal,
  refusalId,
}: {
  count: number
  limit: number
  refusal: Refusal | null
  refusalId: string
}) {
  const { t } = useTranslation()

  if (refusal) {
    return (
      <p id={refusalId} className="max-w-prose text-sm text-ink">
        {refusal === 'noName'
          ? t('search.noName')
          : t(refusal === 'tooMany' ? 'search.tooMany' : 'search.tooManyNames', {
              queries: count,
              limit,
            })}
      </p>
    )
  }
  if (count === 0) return null
  return (
    <p className="max-w-prose text-xs text-ink-dim">{t('search.costWait', { count })}</p>
  )
}

/**
 * 按了一顆名字 chip：別名以外的種類照它記住（同一顆兩種時兩種都記）。別名沒有語言，記住「別名」等於
 * 下一部作品三十幾個全開，所以不記。
 */
function rememberKinds(
  chip: NameChip,
  on: boolean,
  remember: (kinds: Partial<Record<NameKind, boolean>>) => void,
) {
  const kinds = chip.kinds.filter((kind) => kind !== 'alias')
  if (kinds.length > 0) remember(Object.fromEntries(kinds.map((kind) => [kind, on])))
}

/**
 * 缺集搜尋分批時，問完一批之後的那一行（M3 票 20）：這一批問了哪幾季、下一批是哪幾季。
 */
function BatchLine({ batch, onNext }: { batch: Batch; onNext: (fromSeason: number) => void }) {
  const { t } = useTranslation()
  const seasons = seasonList(t, batch.seasons)

  return (
    <div className="grid max-w-prose gap-1">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-sm text-ink">
          {t('search.batch.asked', { seasons })}
          {batch.next_seasons.length > 0
            ? t('search.batch.next', {
                later: batch.later,
                seasons: seasonList(t, batch.next_seasons),
              })
            : t('search.batch.last')}
        </span>
        {batch.next_seasons.length > 0 && (
          <button
            type="button"
            onClick={() => onNext(batch.next_seasons[0])}
            className={COMPACT_BUTTON}
          >
            {t('search.batch.ask')}
          </button>
        )}
      </p>
    </div>
  )
}

/** 真的分了批：之後還有，或這一批本來就不是第一批。只有一批的缺集搜尋不說「批」。 */
function isBatched(batch: Batch, missing: MissingScope | null): boolean {
  return batch.later > 0 || (missing?.fromSeason ?? 0) > 0
}

/** `S01、S02、S03`：季號是機器字串，連接詞跟著語言走。 */
function seasonList(t: TFunction, seasons: readonly number[]): string {
  return seasons.map(seasonCode).join(t('search.batch.join'))
}

/**
 * 送單會寫死的資料夾名（plan §5、brief §4.5）。凍結之前是「將會是」，之後是「就是」——兩件事，各自一句
 * 什麼時候定下來（票 04b、09）。
 */
function FolderLine({ media }: { media: Media }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-1">
      <dl className="grid gap-1">
        <dt className="label text-ink-dim">
          {media.folder_frozen ? t('media.folderFrozen') : t('media.folderPreview')}
        </dt>
        {/* 機器字串：之後真的會出現在檔案系統上的那一串，換行不截斷。 */}
        <dd className="value text-sm wrap-anywhere text-ink">{media.folder_name}</dd>
      </dl>
      <p className="max-w-prose text-xs text-ink-dim">
        {media.folder_frozen ? t('media.folderFrozenNote') : t('media.folderNote')}
      </p>
    </div>
  )
}

/**
 * 搜尋結束之後的纜繩。**失敗的一條一條畫**，原文就地展開（The Needs-You Floats Up Rule）；有回應的收成一個
 * `<details>`，摘要說幾個關鍵字有回應、展開才逐條列筆數。全部有回應時整塊只有一行，而且不塗漆
 * （The Usual Stays Unpainted Rule：一份全部正常的清單看不到信號色）。
 */
function Cables({ attempts }: { attempts: readonly SetupStep[] }) {
  const { t } = useTranslation()
  const failed = attempts.filter((attempt) => attempt.status === 'failed')
  const answered = attempts.filter((attempt) => attempt.status !== 'failed')

  return (
    <div className="grid gap-2">
      {failed.length > 0 && (
        <ol className="grid gap-2">
          {failed.map((attempt) => (
            <StepLine
              key={attempt.step}
              label={attempt.step}
              service={t('search.indexers')}
              summary={attempt.detail}
              row={attempt}
            />
          ))}
        </ol>
      )}
      {answered.length > 0 && (
        <details className="group min-w-0">
          <summary className="flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 border-2 border-rule bg-well px-4 py-2.5 marker:content-none">
            <span className="text-sm text-ink">
              {failed.length > 0
                ? t('search.answeredRest', { count: answered.length })
                : t('search.answeredAll', { count: answered.length })}
            </span>
            <ExpandHint className="ms-auto" />
          </summary>
          <ol className="mt-2 grid gap-2">
            {answered.map((attempt) => (
              <StepLine
                key={attempt.step}
                label={attempt.step}
                service={t('search.indexers')}
                summary={attempt.detail}
                row={attempt}
              />
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

/**
 * 還在問的時候那幾條纜繩長什麼樣：關鍵字就是要送出去的那幾個，狀態一律 `working`。
 *
 * 形狀與後端回的 `attempts` 相同，所以同一個 `StepLine` 畫得出來——一有結果就整批換掉，
 * 版面不跳。
 */
function pending(keyword: string, planned: string[] | undefined): SetupStep[] {
  const typed = keyword.trim()
  const steps = typed ? [typed] : (planned ?? [])
  return steps.map((step) => ({ step, status: 'running', detail: '', error: '' }))
}

/**
 * 這一輪的預選 Route。
 *
 * **上次送單用的那一條優先**（`default_route_id`，票 09 寫）：入庫到哪裡是一個會重複的
 * 決定，同一部作品的第二季幾乎一定進同一條 Route。它已經不在（被刪掉了）時落回下一條規則。
 *
 * 其次是「只有一條收得下這部作品」——沒有第二個選項的選擇不該讓使用者做。
 */
function preselected(media: Media): number | null {
  const routes = media.routes
  const last = routes.find((route) => route.id === media.default_route_id)
  if (last) return last.id
  return routes.length === 1 ? routes[0].id : null
}

function failedCount(results: { attempts: readonly { status: string }[] }): number {
  return results.attempts.filter((attempt) => attempt.status === 'failed').length
}

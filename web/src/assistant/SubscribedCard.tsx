import { useContext, useId, type Ref } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Subscribed, Unsubscribed } from '../api/assistant'
import { feedsQueryOptions, RSS_KEY } from '../api/rss'
import { TEXT_LINK } from '../components/controls'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import { useFocusOnSettle } from '../components/useFocusOnSettle'
import { displayRound } from '../i18n/displayRound'
import { excludedText, sentences } from '../media/excludedText'
import { CardFrame, WorkLink } from './cardParts'
import { ToolCallContext } from './toolCall'
import type { ToolOutput } from './transcript'
import { UndoButton } from './UndoButton'

/**
 * 訂閱的結果卡（M5 票 11，DESIGN.md〈助理側面板〉的結果卡）：Feed 卡與它帶到的 RSS Series——名稱、來源、綁到哪部
 * 作品、下一次輪詢。三個訂閱工具（Mikan、Nyaa / acg.rip 搜尋詞、以網址加 Feed）同一種結果。
 *
 * - **下一次輪詢讀現況**（`GET /rss/feeds`，與 RSS 頁同一份）：存下的那一份是訂閱那一刻的，過一輪就不準。Feed
 *   不在清單上了（在 RSS 頁刪了）說一句，不當成錯誤。
 * - 搜尋 feed 的第一輪要人在 RSS 頁選「全部下載」或「只追之後的」（AI 不替人選），卡上指過去。
 * - **撤銷**（2026-10-24 使用者選定）：停掉訂閱，撤回它送出、還沒下載完的 Job；已經下載完的留著。撤銷之後卡片
 *   說撤回了幾筆、留了幾筆，不再讀現況。
 */
export function SubscribedCard({ result }: { result: Subscribed }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const { undone } = useContext(ToolCallContext)
  const feeds = useQuery({ ...feedsQueryOptions(), enabled: undone === null })
  // 撤銷鍵消失了：焦點落在說已撤銷的那一段（M5 票 15）。
  const undoneRef = useFocusOnSettle<HTMLParagraphElement>(undone !== null)
  const live = feeds.data?.find((feed) => feed.id === result.feed.id)
  const gone = feeds.isSuccess && live === undefined
  const excluded = excludedText(t, result.excluded, i18n.language)

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.subscribed.title')}
      count={t(`rss.kind.${result.feed.kind}`)}
    >
      <div className="grid gap-2 px-3 py-2.5">
        <p className="value text-sm wrap-anywhere text-ink">{result.feed.name}</p>
        {result.series.length === 0 && result.media && (
          // 搜尋 feed 還沒讀到、Series 還沒長出來：照訂閱時說的那一部。
          <p className="value text-xs wrap-anywhere text-ink">
            <WorkLink media={result.media}>
              {displayRound(i18n.language, {
                'zh-Hant': result.media_title,
                en: result.media_title_en,
              }) || result.media}
            </WorkLink>
          </p>
        )}
        {result.series.length > 0 && (
          <ul aria-label={t('assistant.cards.subscribed.series')} className="grid gap-1">
            {result.series.map((series) => {
              const title = displayRound(i18n.language, {
                'zh-Hant': series.media_title,
                en: series.media_title_en,
              })
              const group = series.mikan_subgroup_name || series.group
              return (
                <li key={series.id} className="value text-xs wrap-anywhere text-ink">
                  {series.media ? (
                    <WorkLink media={series.media}>{title || series.media}</WorkLink>
                  ) : (
                    <span className="text-ink-dim">{t('assistant.cards.subscribed.unbound')}</span>
                  )}
                  {group && (
                    <>
                      {' '}
                      <Dot /> {group}
                    </>
                  )}
                  {series.route_name && (
                    <>
                      {' '}
                      <Dot /> <span className="text-ink-dim">{series.route_name}</span>
                    </>
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {undone ? (
          <Undone undone={undone} statusRef={undoneRef} />
        ) : (
          <>
            {result.submitted > 0 && (
              <p className="text-xs text-ink">
                {t('assistant.cards.subscribed.submitted', { count: result.submitted })}
              </p>
            )}
            {excluded && <p className="text-xs text-ink-dim">{excluded}</p>}
            {!result.feed.primed && (
              <p className="text-xs text-ink">
                {t('assistant.cards.subscribed.firstRound')}{' '}
                <Link to="/rss" className={TEXT_LINK}>
                  {t('assistant.cards.subscribed.toRss')}
                </Link>
              </p>
            )}
            {gone ? (
              <p className="text-xs text-ink-dim">{t('assistant.cards.subscribed.gone')}</p>
            ) : (
              <p className="text-xs text-ink-dim">
                {t('assistant.cards.subscribed.nextPoll')}{' '}
                <NextPoll
                  polledAt={live?.last_polled_at ?? result.feed.last_polled_at}
                  interval={live?.interval_sec ?? result.feed.interval_sec}
                />
              </p>
            )}
            {/* Feed 在 RSS 頁刪掉了：撤銷只會得到「不在了」，不給鍵。 */}
            {!gone && (
              <UndoButton
                label={t('assistant.cards.subscribed.undo')}
                confirm={t('assistant.cards.subscribed.undoConfirm')}
                invalidate={[RSS_KEY, ['jobs'], ['media']]}
              />
            )}
          </>
        )}
      </div>
    </CardFrame>
  )
}

/**
 * 上一輪加上間隔；還沒輪過、或那個時間已經過了（到期了、背景迴圈還沒輪到它）是「半分鐘內」——背景迴圈每半分鐘
 * 看一次到期的 Feed。不說「下一次輪詢 4 週前」（M5 票 15）。
 */
function NextPoll({ polledAt, interval }: { polledAt: string | null; interval: number }) {
  const { t } = useTranslation()
  const next = polledAt ? new Date(polledAt).getTime() + interval * 1000 : null
  if (next === null || isPast(next)) {
    return <span className="value">{t('assistant.cards.subscribed.soon')}</span>
  }
  return <Timestamp at={new Date(next).toISOString()} />
}

/** 同 `FilesPanel` 的 `overdue`：讀牆上時間放在元件外。 */
function isPast(moment: number): boolean {
  return moment <= Date.now()
}

function Undone({
  undone,
  statusRef,
}: {
  undone: ToolOutput
  statusRef: Ref<HTMLParagraphElement>
}) {
  const { t, i18n } = useTranslation()
  // 依 `type` 讀 `result` 的形狀（同 `ResultCard`）：型別是後端照同一份登記寫的。
  const counts = undone.type === 'Unsubscribed' ? (undone.result as unknown as Unsubscribed) : null
  return (
    <p ref={statusRef} role="status" tabIndex={-1} className="text-xs text-ink">
      {sentences(
        [
          t('assistant.cards.subscribed.undone'),
          counts && counts.removed > 0
            ? t('assistant.cards.subscribed.removed', { count: counts.removed })
            : '',
          counts && counts.kept > 0
            ? t('assistant.cards.subscribed.kept', { count: counts.kept })
            : '',
        ],
        i18n.language,
      )}
    </p>
  )
}

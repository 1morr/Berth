import { useTranslation } from 'react-i18next'

import type { Plan, PlanItem } from '../api/plans'
import { CollapsibleRow } from '../components/CollapsibleRow'
import { Dot } from '../components/Dot'
import { formatCoverage, formatEpisode } from '../components/episodes'
import { FileEntry } from '../components/FileEntry'
import { groupRows, type RowGroup } from '../components/rowGroups'
import { Reasons } from '../plans/Reasons'
import { seriesValuesText } from '../rss/seriesValues'

/**
 * 一筆 Job 的 Import Plan（brief §6.5、票 11）。
 *
 * 它回答的是這一頁最重要的那個問題：**這幾個檔案會被寫到哪裡去**。時間線說的是
 * 「發生過什麼」，這一塊說的是「接下來會發生什麼」，所以它排在時間線前面。
 *
 * **一個檔案一列，包含略過的那些**：一包 torrent 裡有字型、有海報、有 readme，而
 * 「Berth 沒有動它」與「Berth 沒看到它」是兩件事。逐列說得出處置，那份清單才算數。
 * 但逐檔那一列**收在組裡**（M1.5 票 09、`.scratch/m1.5/long-lists-shape.md`，使用者拍板）：一組是「處置 × 季 × 信心 ×
 * 待確認」，一組一行說蓋到哪幾集、幾個檔案，展開才逐檔列出——芙莉蓮 39 個檔案逐檔攤開，這一列展開是 8,500px。
 * 待審、對不到、待確認的組排最前。
 *
 * **這一塊沒有信號色**（The One Meaning Rule）：這一列的狀態格已經在上面塗過一次漆了，
 * 而處置與信心是**分類不是狀態**（The Role Is Not A State Rule）——所以它們是中性色塊
 * 與文字。要人看的那幾列改用**線變重**（`rule-strong`），與失敗那一列同一種語彙。
 */
export function JobPlan({ plan }: { plan: Plan }) {
  const { t } = useTranslation()
  const reason = plan.summary.review_reason
  const seriesValues = plan.series ? seriesValuesText(t, plan.series) : null

  return (
    <section className="grid min-w-0 gap-2">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="label text-ink">{t('jobs.plan.title')}</span>
        {/* 計劃的狀態是**分類**：這一列的 Job 狀態已經說過「待審核 / 入庫中」了。 */}
        <span className="label bg-deck px-1.5 py-0.5 text-ink">
          {t(`jobs.plan.status.${plan.status}`)}
        </span>
        <span className="value text-xs text-ink-dim">
          {t('jobs.plan.planned', { count: plan.summary.files ?? 0 })}
        </span>
        <Dot />
        <span className="value text-xs text-ink-dim">
          {t('jobs.plan.levels', {
            high: plan.summary.high ?? 0,
            medium: plan.summary.medium ?? 0,
            low: plan.summary.low ?? 0,
          })}
        </span>
      </p>

      {/* 預估與「為什麼停下來」各自一句話，而且**只在成立時出現**——常態不需要旁白。 */}
      {plan.status === 'preplan' && (
        <p className="max-w-prose text-xs text-ink-dim">{t('jobs.plan.estimate')}</p>
      )}
      {reason && (
        <p className="max-w-prose text-xs text-ink-dim">{t(`jobs.plan.reason.${reason}`)}</p>
      )}
      {/* RSS 送的那一份算的時候照了 Series 的季號與偏移（M3 票 13）：值是規劃那一刻讀的，之後改了
          Series，這一份仍說它當時用了什麼——同一個 Series 前後兩份不一樣時看得出來。 */}
      {plan.series && (
        <p className="max-w-prose text-xs text-ink-dim">
          {seriesValues !== null
            ? t('jobs.plan.series', { values: seriesValues })
            : t('jobs.plan.seriesUnset')}
        </p>
      )}

      <div className="grid gap-px bg-rule">
        {byDecision(plan.items).map((group) => (
          <PlanGroup key={group.key} group={group} />
        ))}
      </div>
    </section>
  )
}

/** 需要人的那幾列：待審、對不到，以及已經入庫、但 medium 那一個判斷還要人看一眼的（brief §6.5、票 15）。 */
function held(item: PlanItem): boolean {
  return item.action === 'review' || item.action === 'unmatched' || item.audit
}

function byDecision(items: readonly PlanItem[]): RowGroup<PlanItem>[] {
  return groupRows(
    items,
    (item) => [item.action, item.season ?? '', item.confidence, item.audit].join(':'),
    held,
  )
}

/** 一組：處置 · 信心 · 待確認 · 蓋到的集 · 檔案數。組裡的逐檔列照舊（理由逐檔不同，不合併）。 */
function PlanGroup({ group }: { group: RowGroup<PlanItem> }) {
  const { t } = useTranslation()
  const [first] = group.rows
  const action = t(`jobs.plan.action.${first.action}`)
  const coverage = formatCoverage(first.season, group.rows)

  return (
    <CollapsibleRow
      name={[action, coverage].filter(Boolean).join(' ')}
      held={group.held}
      summary={
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="label bg-deck px-1.5 py-0.5 text-ink">{action}</span>
          <span className="label text-ink-dim">
            {t(`jobs.plan.confidence.${first.confidence}`)}
          </span>
          {first.audit && (
            <>
              <Dot />
              <span className="value text-xs text-ink">{t('jobs.plan.audit')}</span>
            </>
          )}
          {coverage && (
            <>
              <Dot />
              <span className="value text-sm text-ink">{coverage}</span>
            </>
          )}
          <Dot />
          <span className="value text-xs text-ink-dim">
            {t('jobs.plan.files', { count: group.rows.length })}
          </span>
        </span>
      }
    >
      {() => (
        <ol className="grid min-w-0 gap-2 px-4 py-3">
          {group.rows.map((item) => (
            <PlanRow key={item.id} item={item} />
          ))}
        </ol>
      )}
    </CollapsibleRow>
  )
}

/**
 * 逐檔的一列：**摘要是季集 · 來源檔名**，目標路徑與理由收在裡面（M1.5 票 09b）。
 *
 * 處置、信心與待確認**是組鍵的一部分**（`byDecision`），一組裡必然相同——組的摘要說過了，這一列
 * 不再重複。留在外面的來源檔名是使用者認得出這個檔案的東西：一包 torrent 裡有字型、有海報、有
 * readme，少了它那幾列的「略過」長得一模一樣。
 *
 * 版面與時間線的一筆刻意相同（左邊一條線 + 內縮）：它們在同一塊展開區裡，長得不一樣
 * 只會讓人以為那是另一種東西。
 */
function PlanRow({ item }: { item: PlanItem }) {
  const { t } = useTranslation()
  const episode = formatEpisode(item)

  return (
    // 需要人的那幾列**線變重，不是變紅**：紅色只代表阻擋（The One Meaning Rule）。
    <FileEntry
      heavy={held(item)}
      summary={
        <>
          {episode && <span className="value text-xs text-ink">{episode}</span>}
          {/* 來源檔名整條換行，不截斷（票 08 §8 的同一條）。 */}
          <span className="value min-w-0 text-xs wrap-anywhere text-ink">{item.rel_path}</span>
        </>
      }
    >
      {item.target_path && (
        <p className="value text-xs wrap-anywhere text-ink-dim">
          <span className="label mr-2 text-ink-dim">{t('jobs.plan.target')}</span>
          {item.target_path}
        </p>
      )}

      {/* 理由是封閉集合的 code + 參數，句子在前端（M2 票 07，`plans/reasonText.ts`）。 */}
      <Reasons reasons={item.reasons} />
    </FileEntry>
  )
}

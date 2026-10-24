import type { ComponentType } from 'react'
import { ErrorBoundary } from 'react-error-boundary'
import { useTranslation } from 'react-i18next'

import type { ToolResults, ToolResultType } from '../api/assistant'
import { MissingEpisodesCard } from './MissingEpisodesCard'
import { ProposalCardView } from './ProposalCard'
import { RecentImportsCard } from './RecentImportsCard'
import { SearchResultsCard } from './SearchResultsCard'
import { SubmittedJobCard } from './SubmittedJobCard'
import type { ToolOutput } from './transcript'

/**
 * 結果卡（M5 票 09，CONTEXT.md 的 Result Card）：**依工具結果的型別挑元件，不依模型寫的字。**
 *
 * 一種結果型別一格。型別的封閉集合由後端從命令登錄表產生（`ToolResultType`），所以後端登記了新的
 * 結果型別、這裡沒跟上時 `tsc` 紅——加一種卡就是在這裡加一格。`null` 是這一種不畫卡：`Refusal` 的
 * 理由已經在工具狀態行上。
 */
const CARDS: { [K in ToolResultType]: ComponentType<{ result: ToolResults[K] }> | null } = {
  RecentImports: RecentImportsCard,
  MissingEpisodes: MissingEpisodesCard,
  SearchResults: SearchResultsCard,
  SubmittedJob: SubmittedJobCard,
  // 要人按的工具只在確認之後才有結果：那時結果畫在確認卡裡（`ProposalCard` 的 `Outcome`），
  // 工具結果裡永遠是那一張卡，不會是它們。
  IndexerAdded: null,
  DownloadsDeleted: null,
  Refusal: null,
  ProposalCard: ProposalCardView,
}

/**
 * **退路**：認不得的型別（舊版本存下、這一版拿掉了）與畫到一半丟錯的卡（存下的結果是舊的形狀）
 * 都只剩工具狀態行那一句摘要，加一行說這裡畫不出卡片——不壞整個對話。
 */
export function ResultCard({ output }: { output: ToolOutput }) {
  if (!Object.hasOwn(CARDS, output.type)) return <NoCard />
  // 依 `type` 取出的那一格與 `result` 的形狀，TypeScript 對不起來（相關聯的聯集）；`type` 是後端
  // 照同一份登記寫的，形狀不合的由下面的 ErrorBoundary 接住。
  const Card = CARDS[output.type as ToolResultType] as ComponentType<{ result: unknown }> | null
  if (Card === null) return null
  return (
    <ErrorBoundary fallback={<NoCard />}>
      <Card result={output.result} />
    </ErrorBoundary>
  )
}

function NoCard() {
  const { t } = useTranslation()
  return <p className="text-xs text-ink-dim">{t('assistant.cards.unknown')}</p>
}

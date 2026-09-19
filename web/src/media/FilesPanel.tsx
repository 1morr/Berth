import { useId } from 'react'
import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { CollapsibleRow } from '../components/CollapsibleRow'
import { GHOST_LINK } from '../components/controls'
import { Dot } from '../components/Dot'
import { formatCoverage, formatEpisode } from '../components/episodes'
import { FileEntry } from '../components/FileEntry'
import { groupRows, type RowGroup } from '../components/rowGroups'
import { Timestamp } from '../components/Timestamp'

type LedgerFile = Media['files'][number]

/**
 * 檔案與版本（`.scratch/m1/library-shape.md` §5，Media 詳情區塊序列的第 4 塊）。
 *
 * 它回答的是「這部作品在媒體庫裡**實際上**有什麼」：季集表說的是每一集的狀態，這一塊說的是
 * 每一個檔案——它蓋到哪一集、帶什麼 Tags、落在哪條路徑、帳本對不對得上、Jellyfin 找到了沒。
 *
 * 劇集**依決定分組**（M1.5 票 09、`.scratch/m1.5/long-lists-shape.md`，使用者拍板）：一組是「處置 × 季」，一組一行說
 * 蓋到哪幾集、幾個檔案、帳本與 Jellyfin；逐檔要展開那一組才畫（芙莉蓮一季 28 個檔案逐檔攤開是 3,800px）。
 * 帳本對不上、Jellyfin 找不到的那一組排最前。電影的檔案是一兩個，不分組。對不到的檔案排在最後——它們不在媒體庫裡，
 * 只是需要人知道它們在哪。
 */
export function FilesPanel({ media }: { media: Media }) {
  const { t } = useTranslation()
  const headingId = useId()
  const hasFeature = media.files.some((file) => file.action === 'import')

  return (
    <section aria-labelledby={headingId} className="grid gap-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {t('media.files.title')}
        </h2>
        {media.files.length > 0 && (
          // 光一個「10」唸出來沒有意義：看得見的是數字，聽得見的是「共 10 個檔案」。
          <p className="value text-xs text-ink-dim">
            <span aria-hidden="true">{media.files.length}</span>
            <span className="sr-only">{t('media.files.total', { count: media.files.length })}</span>
          </p>
        )}
      </div>

      {media.files.length === 0 && (
        <p className="max-w-prose text-sm text-ink-dim">{t('media.files.none')}</p>
      )}

      {media.files.length > 0 &&
        (media.kind === 'movie' ? (
          <div className="border-2 border-rule bg-well px-4 py-3">
            <FileList files={media.files} summarised={false} />
          </div>
        ) : (
          <div className="grid gap-px bg-rule">
            {byDecision(media.files).map((group) => (
              <FileGroup key={group.key} group={group} />
            ))}
          </div>
        ))}

      {hasFeature && (
        <div className="grid gap-2">
          <h3 className="label text-ink">{t('media.files.versions.title')}</h3>
          {media.versions.length === 0 ? (
            // 常態也說一句：「沒有多版本」與「這一塊還沒畫出來」看起來不能一樣（shape brief §5）。
            <p className="max-w-prose text-xs text-ink-dim">
              {media.kind === 'movie'
                ? t('media.files.versions.noneMovie')
                : t('media.files.versions.noneTv')}
            </p>
          ) : (
            <>
              <p className="max-w-prose text-xs text-ink-dim">{t('media.files.versions.note')}</p>
              <ul className="grid gap-3">
                {media.versions.map((group) => (
                  <li
                    key={`${group.season}-${group.episode_start}-${group.episode_end}`}
                    className="grid min-w-0 gap-1 border-l-2 border-rule pl-3"
                  >
                    {formatEpisode(group) && (
                      <p className="value text-xs text-ink">{formatEpisode(group)}</p>
                    )}
                    {/* 版本名是 **Jellyfin 算的**（brief §7.7）：整條換行，不截斷。它還沒收錄
                        的那幾個沒有名字，顯示檔名的 tags 並在底下說一句，不自己重算一個。 */}
                    {/* key 用位置：這一組是一次讀出來的快照，不排序也不增刪，而兩個版本的
                        名字與 tags 都可能是空的（Jellyfin 還沒收錄、檔名也沒有 tag）。 */}
                    <ul className="grid gap-0.5">
                      {group.versions.map((version, index) => (
                        <li key={index} className="value text-xs wrap-anywhere text-ink-dim">
                          {version.name || version.tags || '—'}
                        </li>
                      ))}
                    </ul>
                    {group.versions.some((version) => !version.name) && (
                      <p className="max-w-prose text-xs text-ink-dim">
                        {t('media.files.versions.pending')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {media.unmatched.length > 0 && (
        <div className="grid justify-items-start gap-2">
          <h3 className="label text-ink">{t('media.files.unmatched.title')}</h3>
          <p className="max-w-prose text-xs text-ink-dim">{t('media.files.unmatched.note')}</p>
          <ul className="grid w-full gap-2">
            {media.unmatched.map((row) => (
              // 需要人知道的那幾列線變重，不是變紅（The One Meaning Rule，與 `JobPlan` 同一種）。
              <li
                key={`${row.job_hash}-${row.rel_path}`}
                className="grid min-w-0 gap-0.5 border-l-2 border-rule-strong pl-3"
              >
                <p className="value text-xs wrap-anywhere text-ink">{row.rel_path}</p>
                <p className="value text-xs wrap-anywhere text-ink-dim">{row.job_name}</p>
              </li>
            ))}
          </ul>
          <Link to="/jobs" className={GHOST_LINK}>
            {t('media.files.unmatched.toJobs')}
          </Link>
        </div>
      )}
    </section>
  )
}

/**
 * 一組：處置 · 蓋到的集 · 檔案數 · 帳本 · Jellyfin。
 *
 * 帳本與 Jellyfin 是這一組的**計數**：常態說一句「帳本對得上」「Jellyfin 已收錄 28」，例外說幾個（是 0 的不說）。
 * Jellyfin 那一格只算正片——字幕與特典不查（`presence` 是 `none`），整組都不查時那一格不畫。
 */
function FileGroup({ group }: { group: RowGroup<LedgerFile> }) {
  const { t } = useTranslation()
  const [first] = group.rows
  const coverage = formatCoverage(first.season, group.rows)
  const action = actionLabel(t, first)
  const off = group.rows.filter((file) => file.status !== 'ok').length
  const seen = (kind: LedgerFile['presence']) =>
    group.rows.filter((file) => file.presence === kind).length
  const facts = [
    t('media.files.count', { count: group.rows.length }),
    off === 0 ? t('media.files.ledger.allOk') : t('media.files.ledger.off', { count: off }),
    ...(['found', 'searching', 'lost'] as const)
      .filter((kind) => seen(kind) > 0)
      .map((kind) => t(`media.files.jellyfin.${kind}Count`, { count: seen(kind) })),
  ]

  return (
    <CollapsibleRow
      name={[action, coverage].filter(Boolean).join(' ')}
      held={group.held}
      summary={
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          {/* 處置是分類不是狀態：中性色塊（The Role Is Not A State Rule）。 */}
          <span className="label bg-deck px-1.5 py-0.5 text-ink">{action}</span>
          {coverage && <span className="value text-sm text-ink">{coverage}</span>}
          {facts.map((fact) => (
            <span key={fact} className="contents">
              <Dot />
              <span className="value text-xs text-ink-dim">{fact}</span>
            </span>
          ))}
        </span>
      }
    >
      {() => (
        <div className="px-4 py-3">
          <FileList files={group.rows} summarised />
        </div>
      )}
    </CollapsibleRow>
  )
}

/** S00 的正片是 Specials（TMDB season 0），不是「正片」也不是 extras（CONTEXT.md）。 */
function actionLabel(t: TFunction, file: LedgerFile): string {
  return file.action === 'import' && file.season === 0
    ? t('media.files.special')
    : t(`media.files.action.${file.action}`)
}

/** `summarised`：上面有一行組摘要說過處置、帳本與 Jellyfin 了嗎？電影不分組，所以是 `false`。 */
function FileList({ files, summarised }: { files: readonly LedgerFile[]; summarised: boolean }) {
  return (
    <ol className="grid min-w-0 gap-3">
      {files.map((file) => (
        <FileRow key={file.id} file={file} summarised={summarised} />
      ))}
    </ol>
  )
}

/**
 * 一個檔案：**摘要一行是處置 · 季集 · 檔名 · 帳本 · Jellyfin**，Tags 與完整路徑收在裡面（M1.5 票 09b）。
 *
 * 規則只有一條：**上面的摘要說過而且是常態值的，這一列不再說**。所以在組裡（`summarised`）只剩季集、
 * 檔名與例外——處置是組鍵的一部分，帳本「對得上」與 Jellyfin「已收錄」由組的計數說過了；例外留著，
 * 因為組數得出幾個卻說不出是哪一個。電影不分組，上面沒有人說，所以每一格都自己說。
 *
 * 資料夾整組共用，外面只留檔名——那一段才是這一筆與隔壁那一筆不同的地方。
 */
function FileRow({ file, summarised }: { file: LedgerFile; summarised: boolean }) {
  const { t } = useTranslation()
  const episode = formatEpisode(file)

  return (
    <FileEntry
      summary={
        <>
          {!summarised && (
            // 處置是分類不是狀態：中性色塊（The Role Is Not A State Rule）。
            <span className="label bg-deck px-1.5 py-0.5 text-ink">{actionLabel(t, file)}</span>
          )}
          {episode && <span className="value text-xs text-ink">{episode}</span>}
          {/* 檔名整條換行，不截斷：它是使用者認得出這個檔案的東西（票 08 §8 的同一條）。 */}
          <span className="value min-w-0 text-xs wrap-anywhere text-ink">{baseName(file)}</span>
          <Facts file={file} summarised={summarised} />
        </>
      }
    >
      <Labelled label={t('media.files.tags')} value={file.tags} />
      <Labelled label={t('media.files.target')} value={file.target_path} />
    </FileEntry>
  )
}

/**
 * 帳本與 Jellyfin。在組裡時只說例外——常態的那兩句組的摘要已經數過了。
 *
 * 兩邊都沒話說時**整個不畫**：空的 `<span>` 仍然是一個 flex 項目，會在檔名後面多撐一個 `gap-x-2`。
 */
function Facts({ file, summarised }: { file: LedgerFile; summarised: boolean }) {
  const { t } = useTranslation()
  const ledger = !summarised || file.status !== 'ok'

  if (!ledger && !saysPresence(file, summarised)) return null
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      {ledger && (
        <>
          <Dot />
          <span className="label text-ink-dim">{t('media.files.ledger.label')}</span>
          <span className="text-ink">{t(`media.files.ledger.${file.status}`)}</span>
        </>
      )}
      <Presence file={file} summarised={summarised} />
    </span>
  )
}

/** 收起來的那幾行：每一格自己說出它是什麼，沒有欄頭時一串路徑說不出自己是目標還是來源。 */
function Labelled({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <p className="value text-xs wrap-anywhere text-ink-dim">
      <span className="label mr-2 text-ink-dim">{label}</span>
      {value}
    </p>
  )
}

/** 目標路徑的最後一段。資料夾是整組共用的，所以摘要上只留這一段（票 09 的 Comments）。 */
function baseName(file: LedgerFile): string {
  return file.target_path.split('/').pop() || file.target_path
}

/**
 * 這一列要不要說 Jellyfin 那一格。字幕與特典不查（`presence` 是 `none`）；**在組裡時「已收錄」也不說**
 * ——那是常態，而組的摘要已經數過了（「Jellyfin 已收錄 28」）。另外兩種在組裡也留著，因為它們各自帶一個
 * 組數不出來的值：下一次什麼時候查、試了幾次。
 *
 * `Facts` 要先知道整行會不會是空的，所以這個判準單獨一份，不寫在 `Presence` 裡（M1.5 票 09b）。
 */
function saysPresence(file: LedgerFile, summarised: boolean): boolean {
  if (file.presence === 'none') return false
  return !(summarised && file.presence === 'found')
}

/** Jellyfin 找到這個檔案了沒（要不要說由 `saysPresence` 決定）。 */
function Presence({ file, summarised }: { file: LedgerFile; summarised: boolean }) {
  const { t } = useTranslation()

  if (!saysPresence(file, summarised)) return null
  return (
    <>
      <Dot />
      {file.presence === 'found' ? (
        <span className="text-ink">{t('media.files.jellyfin.found')}</span>
      ) : file.presence === 'searching' ? (
        <span className="text-ink-dim">
          {t('media.files.jellyfin.searching')} <Timestamp at={file.resolve_after} />
        </span>
      ) : (
        <span className="text-ink">
          {t('media.files.jellyfin.lost', { count: file.resolve_attempts })}
        </span>
      )}
    </>
  )
}

/**
 * 「處置 × 季」分組。組照後端的順序（季號小的在前、沒有季號的殿後）；帳本對不上或 Jellyfin 找不到的組排到最前。
 * 正片在 S00 與 S01 是兩組：特別篇與正篇是兩件事（上面的 `actionLabel`）。
 */
function byDecision(files: readonly LedgerFile[]): RowGroup<LedgerFile>[] {
  return groupRows(
    files,
    (file) => `${file.action}:${file.season ?? ''}`,
    (file) => file.status !== 'ok' || file.presence === 'lost',
  )
}

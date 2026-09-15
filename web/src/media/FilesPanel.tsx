import { useId } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { GHOST_LINK } from '../components/controls'
import { Dot } from '../components/Dot'
import { formatEpisode, seasonCode } from '../components/episodes'
import { Timestamp } from '../components/Timestamp'

type LedgerFile = Media['files'][number]

/**
 * 檔案與版本（`.scratch/m1/library-shape.md` §5，Media 詳情區塊序列的第 4 塊）。
 *
 * 它回答的是「這部作品在媒體庫裡**實際上**有什麼」：季集表說的是每一集的狀態，這一塊說的是
 * 每一個檔案——它蓋到哪一集、帶什麼 Tags、落在哪條路徑、帳本對不對得上、Jellyfin 找到了沒。
 *
 * 劇集依季分組、預設全收（與季集表同一個理由：一季的檔案可以是幾十個）；電影的檔案是一兩個，
 * 不分組。對不到的檔案排在最後——它們不在媒體庫裡，只是需要人知道它們在哪。
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
            <FileList files={media.files} />
          </div>
        ) : (
          <div className="grid gap-px bg-rule">
            {bySeason(media.files).map(([season, files]) => (
              // `min-w-0`：grid 項目預設不肯縮，長路徑會把整頁撐寬（票 04 踩過的同一個坑）。
              <details key={season ?? 'none'} className="min-w-0 bg-well">
                <summary className="flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 marker:content-none">
                  <span className="value text-sm font-semibold text-ink">
                    {season === null ? '—' : seasonCode(season)}
                  </span>
                  <span className="value text-xs text-ink-dim">
                    {t('media.files.count', { count: files.length })}
                  </span>
                </summary>
                <div className="border-t-2 border-rule bg-hull px-4 py-3">
                  <FileList files={files} />
                </div>
              </details>
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
                    key={`${group.season}-${group.episode_start}-${group.episode_end}-${group.labels[0]}`}
                    className="grid min-w-0 gap-1 border-l-2 border-rule pl-3"
                  >
                    {formatEpisode(group) && (
                      <p className="value text-xs text-ink">{formatEpisode(group)}</p>
                    )}
                    {/* 版本名就是 Jellyfin 選單上的那一串（brief §7.7）：整條換行，不截斷。 */}
                    <ul className="grid gap-0.5">
                      {group.labels.map((label) => (
                        <li key={label} className="value text-xs break-words text-ink-dim">
                          {label}
                        </li>
                      ))}
                    </ul>
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
                <p className="value text-xs break-words text-ink">{row.rel_path}</p>
                <p className="value text-xs break-words text-ink-dim">{row.job_name}</p>
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

function FileList({ files }: { files: readonly LedgerFile[] }) {
  return (
    <ol className="grid min-w-0 gap-3">
      {files.map((file) => (
        <FileRow key={file.id} file={file} />
      ))}
    </ol>
  )
}

/** 一個檔案：處置 · 季集 · Tags，底下是目標路徑，再底下是帳本與 Jellyfin。 */
function FileRow({ file }: { file: LedgerFile }) {
  const { t } = useTranslation()
  const episode = formatEpisode(file)

  return (
    <li className="grid min-w-0 gap-1 border-l-2 border-rule pl-3">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {/* 處置是分類不是狀態：中性色塊（The Role Is Not A State Rule）。 */}
        <span className="label bg-deck px-1.5 py-0.5 text-ink">
          {t(`media.files.action.${file.action}`)}
        </span>
        {episode && (
          <>
            <Dot />
            <span className="value text-xs text-ink">{episode}</span>
          </>
        )}
        {file.tags && (
          <>
            <Dot />
            <span className="value text-xs break-words text-ink">{file.tags}</span>
          </>
        )}
      </p>
      <p className="value text-xs break-words text-ink-dim">{file.target_path}</p>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span className="label text-ink-dim">{t('media.files.ledger.label')}</span>
        <span className="text-ink">{t(`media.files.ledger.${file.status}`)}</span>
        <Presence file={file} />
      </p>
    </li>
  )
}

/** Jellyfin 找到這個檔案了沒。字幕與特典不查，所以什麼都不說。 */
function Presence({ file }: { file: LedgerFile }) {
  const { t } = useTranslation()

  if (file.presence === 'none') return null
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

/** 依季分組，季號小的在前、沒有季號的（特典）殿後——後端已經照這個順序排好了。 */
function bySeason(files: readonly LedgerFile[]): Array<[number | null, LedgerFile[]]> {
  const groups = new Map<number | null, LedgerFile[]>()
  for (const file of files) {
    const group = groups.get(file.season) ?? []
    group.push(file)
    groups.set(file.season, group)
  }
  return [...groups.entries()]
}

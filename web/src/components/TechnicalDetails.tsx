import { useTranslation } from 'react-i18next'

/**
 * 「技術細節」：端點、實測值、服務回的原文（M4 票 21，`.scratch/m4/error-layers-shape.md`）。
 *
 * **後端的字串只在這裡出現**：人話由代碼選 i18n 文案，掛在造成它的那一條上；原文、HTTP 狀態、
 * errno、inode 收進這個預設收起的原生 `<details>`——Windows / macOS 錯誤對話框的「詳細資訊」、
 * GitHub Actions 每個 step 都能展開 log 的做法。要查證或回報的人展開，其他人不被英文淹沒。
 * `web/eslint.config.js` 擋精靈與設定頁把 `.error` / `.message` 直接當子節點畫出來。
 *
 * 通過的那一列把它放在行尾（`inline`）：收著時是一個小標籤，展開時換到自己一整行。
 */
export function TechnicalDetails({
  lines,
  inline = false,
}: {
  /** 一行一個機器字串。空的略過；全空就什麼都不畫。 */
  lines: ReadonlyArray<string | null | undefined | false>
  inline?: boolean
}) {
  const { t } = useTranslation()
  const shown = lines.filter((line): line is string => typeof line === 'string' && line !== '')
  if (shown.length === 0) return null

  return (
    <details
      data-testid="technical-details"
      className={`min-w-0 ${inline ? 'ml-auto open:ml-0 open:basis-full' : 'mt-4'}`}
    >
      <summary className="label cursor-pointer text-ink-dim hover:text-ink">
        {t('technical.title')}
      </summary>
      <div className="mt-2 grid gap-1 border-2 border-rule bg-hull px-3 py-2">
        {shown.map((line, index) => (
          // 同一列裡的字串可能重複（端點與原文開頭一樣），所以鍵帶位置。
          <p key={`${index}:${line}`} className="value text-xs wrap-anywhere text-ink-dim">
            {line}
          </p>
        ))}
      </div>
    </details>
  )
}

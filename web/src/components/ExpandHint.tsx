import { useTranslation } from 'react-i18next'

/**
 * 可展開列摘要上的「展開 / 收起」（DESIGN.md 的 The Summary Is One Button Rule）。
 *
 * 這幾列的 `<summary>` 都拿掉了 marker（它在窄版會把整列推歪），所以「這一列展得開」要用字說。
 * 切換靠 CSS 的 `group-open`：外層的 `<details>` 要帶 `group`。
 */
export function ExpandHint({ className = '' }: { className?: string }) {
  const { t } = useTranslation()

  return (
    <>
      <span className={`label shrink-0 text-ink-dim group-open:hidden ${className}`}>
        {t('common.expand')}
      </span>
      <span className={`label hidden shrink-0 text-ink-dim group-open:inline ${className}`}>
        {t('common.collapse')}
      </span>
    </>
  )
}

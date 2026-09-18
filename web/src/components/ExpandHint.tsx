import { useTranslation } from 'react-i18next'

/**
 * 可展開列摘要上的「展開 / 收起」（DESIGN.md 的 The Summary Is One Button Rule）。
 *
 * 這幾列的 `<summary>` 都拿掉了 marker（它在窄版會把整列推歪），所以「這一列展得開」要用字說。
 *
 * **兩種切換方式，一份文案與一份樣式**：呼叫端自己有開合狀態時（`CollapsibleRow`）給 `open`；
 * 沒有的就靠 CSS 的 `group-open`（外層的 `<details>` 要帶 `group`）。`CollapsibleRow` 不能用後者
 * ——計劃的組長在下載列那個帶 `group` 的 `<details>` 裡，`group-open:` 會跟著外面那一層亮。
 */
export function ExpandHint({ className = '', open }: { className?: string; open?: boolean }) {
  const { t } = useTranslation()

  if (open !== undefined) {
    return (
      <span className={`label shrink-0 text-ink-dim ${className}`}>
        {open ? t('common.collapse') : t('common.expand')}
      </span>
    )
  }
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

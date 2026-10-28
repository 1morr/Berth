import { useQuery } from '@tanstack/react-query'
import { isTextUIPart, type UIMessage } from 'ai'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { agentRefusalOf, readConversation, stopTurn } from '../api/agent'
import { GhostButton, Notice, TEXT_LINK } from '../components/controls'
import { usePanel } from './panelState'

/** 被擋下時說的那一段對話：第一句話最多幾個字。 */
const TITLE_LENGTH = 40

/**
 * 每人同時一輪（M5 票 25）：送出被擋下（`busy`），而在跑的是另一段對話（例如開了新對話之後）。說出是
 * 哪一段（對話沒有標題，用它的第一句話），可以接過去看它答完，或停掉那一輪再重送這一則。
 * `other` 是伺服器說的那一段對話的 id：位子以人為單位，只會是自己的。
 */
export function BusyElsewhere({ other, onStopped }: { other: string; onStopped: () => void }) {
  const { t } = useTranslation()
  const { switchTo } = usePanel()
  const [stopping, setStopping] = useState(false)
  const [failed, setFailed] = useState(false)
  const found = useQuery({
    queryKey: ['agent', 'conversation-title', other],
    queryFn: async ({ signal }) => firstLine((await readConversation(other, signal))?.messages),
  })
  const title = found.data ?? t('agent.failure.busyUntitled')

  async function stopThatTurn() {
    setStopping(true)
    setFailed(false)
    try {
      await stopTurn(other)
      onStopped()
    } catch (error) {
      // 剛好答完了：已經沒有在跑，一樣可以重送。
      if (agentRefusalOf(error)?.reason === 'not_running') onStopped()
      else setFailed(true)
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="grid gap-2">
      <Notice signal="assigned" label={t('agent.failure.waitLabel')}>
        {t('agent.failure.busyElsewhere', { title })}
      </Notice>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="grid w-40">
          <GhostButton type="button" busy={stopping} onClick={() => void stopThatTurn()}>
            {t('agent.failure.busyStop')}
          </GhostButton>
        </div>
        <button type="button" className={TEXT_LINK} onClick={() => switchTo(other)}>
          {t('agent.failure.busyOpen')}
        </button>
      </div>
      {failed ? <p className="text-sm text-ink">{t('agent.failure.busyStopFailed')}</p> : null}
    </div>
  )
}

/** 一段對話的第一句使用者的話（第一行，太長截斷）；讀不到、沒有字是 `null`。 */
function firstLine(messages: UIMessage[] | undefined): string | null {
  for (const message of messages ?? []) {
    if (message.role !== 'user') continue
    const text = message.parts
      .filter(isTextUIPart)
      .map((part) => part.text)
      .join('')
      .trim()
      .split('\n')[0]
    if (text) return text.length > TITLE_LENGTH ? `${text.slice(0, TITLE_LENGTH)}…` : text
  }
  return null
}

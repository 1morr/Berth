import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { agentRefusalOf, conversationsQueryOptions, stopTurn } from '../api/agent'
import { GhostButton, Notice, TEXT_LINK } from '../components/controls'
import { usePanel } from './panelState'

/**
 * 每人同時一輪（M5 票 25）：送出被擋下（`busy`），而在跑的是另一段對話（例如開了新對話之後）。說出是
 * 哪一段（對話清單的標題：它的第一句話，M5.5 票 18），可以接過去看它答完，或停掉那一輪再重送這一則。
 * `other` 是伺服器說的那一段對話的 id：位子以人為單位，只會是自己的。
 */
export function BusyElsewhere({ other, onStopped }: { other: string; onStopped: () => void }) {
  const { t } = useTranslation()
  const { switchTo } = usePanel()
  const [stopping, setStopping] = useState(false)
  const [failed, setFailed] = useState(false)
  // 在跑的那一段開輪時更新過，一定排在清單最前面幾段。
  const found = useQuery({
    ...conversationsQueryOptions,
    select: (entries) => entries.find((entry) => entry.id === other)?.title || null,
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

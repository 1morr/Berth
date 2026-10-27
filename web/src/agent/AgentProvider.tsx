import { useCallback, useMemo, useState, type ReactNode } from 'react'

import {
  PanelContext,
  readConversationId,
  readOpen,
  rememberNewConversation,
  writeOpen,
  type PanelState,
} from './panelState'

export function AgentProvider({ children }: { children: ReactNode }) {
  const [open, setOpenState] = useState(readOpen)
  const [conversationId, setConversationId] = useState(readConversationId)
  const [restarted, setRestarted] = useState(false)
  const [draft, setDraft] = useState('')

  const setOpen = useCallback((next: boolean) => {
    writeOpen(next)
    setOpenState(next)
  }, [])
  const startNew = useCallback((lost = false) => {
    setRestarted(lost)
    setConversationId(rememberNewConversation())
  }, [])

  const state = useMemo<PanelState>(
    () => ({ open, setOpen, conversationId, startNew, restarted, draft, setDraft }),
    [open, setOpen, conversationId, startNew, restarted, draft],
  )
  return <PanelContext value={state}>{children}</PanelContext>
}

import { useCallback, useMemo, useState, type ReactNode } from 'react'

import {
  PanelContext,
  readConversationId,
  readOpen,
  rememberConversation,
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
  const switchTo = useCallback((id: string) => {
    setRestarted(false)
    setConversationId(rememberConversation(id))
  }, [])

  const state = useMemo<PanelState>(
    () => ({ open, setOpen, conversationId, startNew, switchTo, restarted, draft, setDraft }),
    [open, setOpen, conversationId, startNew, switchTo, restarted, draft],
  )
  return <PanelContext value={state}>{children}</PanelContext>
}

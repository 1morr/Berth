import { beforeEach, describe, expect, it } from 'vitest'

import {
  PANEL_WIDTH_DEFAULT,
  PANEL_WIDTH_MAX,
  PANEL_WIDTH_MIN,
  clampPanelWidth,
  readPanelWidth,
  writePanelWidth,
} from './panelWidth'

// 側面板的寬度（M5.6 票 10b）：上下限、壞掉的值與記在這個瀏覽器的那一格。
describe('panel width', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('starts at the layout width in DESIGN.md', () => {
    expect(PANEL_WIDTH_DEFAULT).toBe(26)
    expect(readPanelWidth()).toBe(PANEL_WIDTH_DEFAULT)
  })

  it('clamps a value back into range, however far out it is', () => {
    expect(clampPanelWidth(5)).toBe(PANEL_WIDTH_MIN)
    expect(clampPanelWidth(99)).toBe(PANEL_WIDTH_MAX)
    expect(clampPanelWidth(Number.NaN)).toBe(PANEL_WIDTH_DEFAULT)
  })

  it('clamps a stored value too: a smaller window or a hand-edited value cannot break the layout', () => {
    localStorage.setItem('berth.agent.width', '12')
    expect(readPanelWidth()).toBe(PANEL_WIDTH_MIN)
    localStorage.setItem('berth.agent.width', '1200')
    expect(readPanelWidth()).toBe(PANEL_WIDTH_MAX)
  })

  it('falls back to the default when what is stored is not a number', () => {
    localStorage.setItem('berth.agent.width', 'wide')
    expect(readPanelWidth()).toBe(PANEL_WIDTH_DEFAULT)
    localStorage.setItem('berth.agent.width', '')
    expect(readPanelWidth()).toBe(PANEL_WIDTH_DEFAULT)
  })

  it('writes the clamped width, rounded to a tenth of a rem', () => {
    writePanelWidth(31.234)
    expect(localStorage.getItem('berth.agent.width')).toBe('31.2')
    writePanelWidth(999)
    expect(readPanelWidth()).toBe(PANEL_WIDTH_MAX)
  })
})

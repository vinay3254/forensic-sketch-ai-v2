// per-browser convenience only: which cases were opened last, and on which page.
// Storage can be missing or blocked, so every access is guarded.
const KEY = 'sketchlab.recent'
const MAX = 6

export interface RecentCase {
  id: number
  path: string // the page last open in that case
  at: number
}

export function recentCases(): RecentCase[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter((r) => typeof r?.id === 'number' && typeof r?.path === 'string') : []
  } catch {
    return []
  }
}

export function rememberVisit(id: number, path: string) {
  try {
    const rest = recentCases().filter((r) => r.id !== id)
    localStorage.setItem(KEY, JSON.stringify([{ id, path, at: Date.now() }, ...rest].slice(0, MAX)))
    window.dispatchEvent(new Event(KEY))
  } catch {
    /* storage unavailable: nothing to remember */
  }
}

export const lastPath = (id: number) => recentCases().find((r) => r.id === id)?.path ?? `/cases/${id}`

export const RECENT_EVENT = KEY

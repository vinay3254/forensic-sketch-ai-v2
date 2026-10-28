import { useQuery } from '@tanstack/react-query'
import { CornerDownLeft, FileText, FolderSearch, UsersRound, Home, MessagesSquare, PenLine, PersonStanding, Plus, Search, Shirt, ShieldCheck, UserRound } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { listCases } from '../api'
import { lastPath } from '../lib/recent'
import { CASE_PAGES } from './caseTabs'

export const OPEN_PALETTE = 'sketchlab.palette'
export const openPalette = () => window.dispatchEvent(new Event(OPEN_PALETTE))

interface Item {
  group: string
  label: string
  hint?: string
  icon: ReactNode
  to: string
}

const PAGE_ICON = { sketch: <PenLine size={15} />, details: <UserRound size={15} />, interview: <MessagesSquare size={15} />, styles: <Shirt size={15} />, figure: <PersonStanding size={15} />, sheet: <FileText size={15} /> }

// ⌘K / Ctrl+K: jump to any case, or straight to one of its pages
export default function CommandPalette({ admin, caseId }: { admin: boolean; caseId: number | null }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const list = useRef<HTMLDivElement>(null)
  const cases = useQuery({ queryKey: ['cases'], queryFn: listCases, enabled: open, staleTime: 30_000 })

  useEffect(() => {
    const show = () => {
      setQ('')
      setActive(0)
      setOpen(true)
    }
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        show()
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener(OPEN_PALETTE, show)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener(OPEN_PALETTE, show)
    }
  }, [])

  const items = useMemo<Item[]>(() => {
    const all: Item[] = [
      { group: 'Go to', label: 'Home', icon: <Home size={15} />, to: '/cases' },
      { group: 'Go to', label: 'New case', hint: 'describe a face', icon: <Plus size={15} />, to: '/cases?new=1' },
      { group: 'Go to', label: 'Criminal records', icon: <FolderSearch size={15} />, to: '/records' },
      ...(admin ? [{ group: 'Go to', label: 'Investigator oversight', icon: <UsersRound size={15} />, to: '/oversight' }] : []),
      ...(admin ? [{ group: 'Go to', label: 'Audit log', icon: <ShieldCheck size={15} />, to: '/audit' }] : []),
    ]
    const current = cases.data?.find((c) => c.id === caseId)
    if (current) {
      all.push(...CASE_PAGES.map((p) => ({ group: 'This case', label: p.label, hint: current.title, icon: PAGE_ICON[p.key], to: p.path(current.id) })))
    }
    for (const c of cases.data ?? []) {
      all.push({ group: 'Cases', label: c.title, hint: c.case_number, icon: <PenLine size={15} />, to: lastPath(c.id) })
    }
    const words = q.toLowerCase().split(/\s+/).filter(Boolean)
    if (words.length) {
      // with a query, every case also offers its pages ("yelahanka sheet")
      for (const c of cases.data ?? []) {
        all.push(...CASE_PAGES.map((p) => ({ group: 'Pages', label: `${c.title} › ${p.label}`, hint: c.case_number, icon: PAGE_ICON[p.key], to: p.path(c.id) })))
      }
    }
    return all.filter((i) => words.every((w) => `${i.label} ${i.hint ?? ''} ${i.group}`.toLowerCase().includes(w)))
  }, [cases.data, caseId, admin, q])

  useEffect(() => {
    list.current?.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  if (!open) return null
  const go = (i: Item | undefined) => {
    if (!i) return
    setOpen(false)
    navigate(i.to)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/20 pt-[12vh] backdrop-blur-[2px]" onMouseDown={() => setOpen(false)}>
      <div
        role="dialog"
        aria-label="Jump to"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-[min(560px,92vw)] overflow-hidden rounded-[22px] border border-ink/10 bg-white/95 shadow-[0_30px_80px_-30px_rgba(40,20,10,0.5)]"
      >
        <label className="flex items-center gap-3 border-b border-black/[0.06] px-5 py-4">
          <Search size={16} className="text-faint" />
          <input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setActive(0)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setActive((a) => Math.min(a + 1, items.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((a) => Math.max(a - 1, 0))
              } else if (e.key === 'Enter') {
                go(items[active])
              } else if (e.key === 'Escape') {
                setOpen(false)
              }
            }}
            placeholder="Jump to a case or page…"
            className="min-w-0 flex-1 border-0 bg-transparent text-[15px] placeholder:text-faint"
          />
          <kbd className="rounded-md border border-line px-1.5 font-mono text-[11px] text-faint">Esc</kbd>
        </label>
        <div ref={list} className="max-h-[50vh] overflow-y-auto p-2">
          {items.length === 0 && <p className="px-3 py-6 text-center text-[13px] text-muted">Nothing matches “{q}”.</p>}
          {items.map((it, i) => (
            <div key={`${it.group}-${it.to}-${it.label}`}>
              {(i === 0 || items[i - 1].group !== it.group) && (
                <div className="px-3 pb-1 pt-2 text-[11px] uppercase tracking-[0.08em] text-faint">{it.group}</div>
              )}
              <button
                data-i={i}
                onMouseMove={() => setActive(i)}
                onClick={() => go(it)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13px] ${i === active ? 'bg-tint text-ink' : 'text-body'}`}
              >
                <span className="text-muted">{it.icon}</span>
                <span className="min-w-0 flex-1 truncate">{it.label}</span>
                {it.hint && <span className="truncate font-mono text-[11px] text-faint">{it.hint}</span>}
                {i === active && <CornerDownLeft size={13} className="text-faint" />}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Search } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { getCase } from '../api'
import { CASE_PAGES, pageOf } from './caseTabs'
import { openPalette } from './CommandPalette'

// one row on every case page: back home, which case this is, its four pages, and jump-to
export default function CaseBar({ caseId }: { caseId: number }) {
  const { pathname } = useLocation()
  const c = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })
  const current = pageOf(pathname)
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-3">
      <Link to="/cases" title="Home" className="grid size-9 place-items-center rounded-full border border-ink/10 bg-white/80 text-body hover:text-ink">
        <ArrowLeft size={16} />
      </Link>
      <div className="flex min-w-0 flex-col leading-tight">
        <span className="font-mono text-[11px] text-faint">{c.data?.case.case_number ?? '…'}</span>
        <span className="max-w-[24ch] truncate text-[14px] font-semibold">{c.data?.case.title ?? ''}</span>
      </div>
      <nav className="flex rounded-full border border-ink/10 bg-white/70 p-1 shadow-[0_6px_20px_-14px_rgba(60,40,30,0.5)]">
        {CASE_PAGES.map((p, i) => (
          <Link
            key={p.key}
            to={p.path(caseId)}
            title={`${p.label} (Alt+${i + 1})`}
            className={`rounded-full px-4 py-1.5 text-[13px] transition-colors ${
              current === p.key ? 'bg-ink font-medium text-white' : 'text-body hover:text-ink'
            }`}
          >
            {p.label}
          </Link>
        ))}
      </nav>
      <button
        onClick={openPalette}
        className="ml-auto flex items-center gap-2 rounded-full border border-ink/10 bg-white/80 px-3.5 py-2 text-[13px] text-faint hover:text-ink"
      >
        <Search size={14} /> Jump to…
        <kbd className="rounded-md border border-line px-1.5 font-mono text-[11px]">Ctrl K</kbd>
      </button>
    </div>
  )
}

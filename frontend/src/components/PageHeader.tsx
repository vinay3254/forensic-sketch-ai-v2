import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

interface Props {
  crumbs: { label: string; to?: string; mono?: boolean }[]
  title: string
  actions?: ReactNode
}

// breadcrumb, page title, case search and the page's main actions
export default function PageHeader({ crumbs, title, actions }: Props) {
  const navigate = useNavigate()
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 px-2 pt-1">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-center gap-2 text-[13px] text-muted">
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-2">
              {i > 0 && <span>/</span>}
              {c.to ? (
                <Link to={c.to} className={`text-muted hover:text-ink ${c.mono ? 'font-mono' : ''}`}>
                  {c.label}
                </Link>
              ) : (
                <span className={`text-ink ${c.mono ? 'font-mono' : ''}`}>{c.label}</span>
              )}
            </span>
          ))}
        </div>
        <h1 className="m-0 truncate text-[26px] font-semibold tracking-[-0.025em]">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const q = new FormData(e.currentTarget).get('q')?.toString().trim() ?? ''
            navigate(q ? `/cases?q=${encodeURIComponent(q)}` : '/cases')
          }}
          className="flex w-[200px] min-w-0 shrink items-center gap-2 rounded-full bg-white px-4 py-[7px]"
        >
          <input name="q" placeholder="Search cases" className="min-w-0 flex-1 border-0 bg-transparent text-[13px] placeholder:text-faint" />
          <span className="rounded-[5px] border border-line px-[5px] py-px font-mono text-[11px] text-faint">⏎</span>
        </form>
        {actions}
      </div>
    </header>
  )
}

export const btnDark =
  'whitespace-nowrap rounded-full border-0 bg-ink px-[18px] py-2.5 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50 cursor-pointer'
export const btnLight =
  'whitespace-nowrap rounded-full border border-[#dcdcd7] bg-white px-4 py-[9px] text-[13px] text-ink hover:border-ink disabled:opacity-50 cursor-pointer'

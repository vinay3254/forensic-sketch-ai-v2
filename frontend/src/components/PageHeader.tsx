import type { ReactNode } from 'react'

interface Props {
  // kept for callers; the case bar above every case page now shows where you are
  crumbs?: { label: string; to?: string; mono?: boolean }[]
  title: string
  actions?: ReactNode
}

// the page's title and its main actions; navigation lives in the case bar and Ctrl K
export default function PageHeader({ title, actions }: Props) {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 px-1">
      <h1 className="m-0 truncate text-[24px] font-semibold tracking-[-0.025em]">{title}</h1>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}

export const btnDark =
  'whitespace-nowrap rounded-full border-0 bg-ink px-[18px] py-2.5 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50 cursor-pointer'
export const btnLight =
  'whitespace-nowrap rounded-full border border-ink/10 bg-white/80 px-4 py-[9px] text-[13px] text-ink hover:border-ink disabled:opacity-50 cursor-pointer'

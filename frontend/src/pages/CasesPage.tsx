import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, MessagesSquare, PenLine, Plus, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMe } from '../App'
import { createCase, listCases, startInterview } from '../api'
import { CASE_PAGES } from '../components/caseTabs'
import Composer from '../components/Composer'
import NewCaseDialog from '../components/NewCaseDialog'
import Sparkle from '../components/Sparkle'
import { lastPath } from '../lib/recent'
import type { Case } from '../types'

const ago = (iso: string) => {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  if (m < 60 * 24) return `${Math.round(m / 60)}h ago`
  return `${Math.round(m / 1440)}d ago`
}

// a case title from the first words of the description
const titleFrom = (text: string) => {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length <= 48 ? t : `${t.slice(0, 45).replace(/\s\S*$/, '')}…`
}

function CaseHistory({ cases, loading, onNew }: { cases: Case[]; loading: boolean; onNew: () => void }) {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const shown = cases.filter((c) => `${c.title} ${c.case_number}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <aside className="flex min-h-0 flex-col gap-4 rounded-[24px] border border-ink/10 bg-white/80 p-4 shadow-[0_10px_40px_-24px_rgba(60,40,30,0.4)]">
      <div className="flex items-center justify-between">
        <h2 className="text-[17px] font-semibold">Case history</h2>
        <button onClick={onNew} title="New case" className="grid size-9 place-items-center rounded-full bg-tint text-body hover:text-ink">
          <Plus size={16} />
        </button>
      </div>
      <label className="flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-2">
        <Search size={14} className="text-faint" />
        <input
          value={q}
          onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })}
          placeholder="Search…"
          className="min-w-0 flex-1 border-0 bg-transparent text-[13px] placeholder:text-faint"
        />
      </label>
      <div className="-mx-1 flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden px-1">
        {shown.length === 0 && (
          <p className="py-6 text-center text-[13px] text-muted">{loading ? 'Loading cases…' : q ? 'No matching cases.' : 'No cases yet.'}</p>
        )}
        {shown.map((c) => (
          <div key={c.id} className="group flex flex-col gap-2 border-b border-black/[0.06] py-3 last:border-0">
            <Link to={lastPath(c.id)} title="Open where you left off" className="flex flex-col gap-2 text-ink">
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-semibold group-hover:text-link">{c.title}</span>
                <span className="truncate text-xs text-muted">
                  <span className="font-mono">{c.case_number}</span> · {c.version_count} version{c.version_count === 1 ? '' : 's'}
                </span>
              </div>
              {c.latest_image_url && (
                <img src={c.latest_image_url} alt="" className="h-24 w-full rounded-[14px] bg-cream object-cover object-[50%_30%] transition group-hover:brightness-95" />
              )}
            </Link>
            <div className="flex flex-wrap items-center gap-1">
              {CASE_PAGES.map((pg) => (
                <Link
                  key={pg.key}
                  to={pg.path(c.id)}
                  className="rounded-full bg-tint px-2 py-0.5 text-[11px] text-body hover:bg-ink hover:text-white"
                >
                  {pg.label === 'Case sheet' ? 'Sheet' : pg.label}
                </Link>
              ))}
              <span className="ml-auto text-[11px] text-faint">{ago(c.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
      <button onClick={onNew} className="rounded-full bg-ink py-3 text-[13px] font-medium text-white shadow-[0_6px_16px_-6px_rgba(0,0,0,0.5)] hover:bg-ink-2">
        Create new case
      </button>
    </aside>
  )
}

export default function CasesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: user } = useMe()
  const { data: cases, error, isPending } = useQuery({ queryKey: ['cases'], queryFn: listCases })
  const [text, setText] = useState('')
  const composer = useRef<HTMLDivElement>(null)
  const focus = () => composer.current?.querySelector('textarea')?.focus()
  const [newOpen, setNewOpen] = useState(false)
  const [params, setParams] = useSearchParams()
  // "New case" from the jump-to palette lands here ready to type
  useEffect(() => {
    if (params.get('new')) {
      setNewOpen(true)
      setParams({}, { replace: true })
    }
  }, [params, setParams])

  // a description starts a case and its first sketch; the workspace draws it on arrival
  const draw = useMutation({
    mutationFn: (description: string) => createCase(titleFrom(description)).then((c) => ({ c, description })),
    onSuccess: ({ c, description }) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate(`/cases/${c.id}`, { state: { description } })
    },
  })
  const interview = useMutation({
    mutationFn: async () => {
      const c = await createCase(`Witness interview ${new Date().toLocaleDateString()}`)
      return { c, iv: await startInterview(c.id) }
    },
    onSuccess: ({ c, iv }) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate(`/cases/${c.id}/interviews/${iv.id}`)
    },
  })
  const lastWithSketch = cases?.find((c) => c.version_count > 0)

  const cards = [
    { icon: <PenLine className="text-ink" />, title: 'Draw a sketch', text: "Type the witness's description and get a pencil sketch", onClick: focus },
    { icon: <MessagesSquare className="text-ink" />, title: 'Interview a witness', text: 'Guided, neutral questions in the witness’s own words', onClick: () => interview.mutate() },
    {
      icon: <FileText className="text-accent" />,
      title: 'Latest case sheet',
      text: lastWithSketch ? `${lastWithSketch.title}` : 'Appears once a case has a sketch',
      onClick: () => lastWithSketch && navigate(`/cases/${lastWithSketch.id}/sheet`),
    },
  ]

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_300px] gap-5">
      <div className="flex min-h-0 flex-col">
        <div className="flex flex-1 flex-col items-center justify-center gap-3 overflow-y-auto px-4 text-center">
          <Sparkle size={130} />
          <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.03em]">Welcome, {user?.username}!</h1>
          <p className="text-[14px] text-muted">Who are we drawing today?</p>
          <div className="mt-8 grid w-full max-w-[640px] grid-cols-3 gap-3 text-left">
            {cards.map((c) => (
              <button
                key={c.title}
                onClick={c.onClick}
                disabled={interview.isPending}
                className="flex flex-col gap-2 rounded-[18px] border border-ink/10 bg-white/80 p-4 text-left shadow-[0_8px_24px_-18px_rgba(60,40,30,0.5)] transition hover:-translate-y-0.5 hover:bg-white"
              >
                <span className="grid size-9 place-items-center rounded-xl bg-tint">{c.icon}</span>
                <span className="mt-2 text-[14px] font-semibold text-ink">{c.title}</span>
                <span className="line-clamp-2 text-[13px] leading-snug text-muted">{c.text}</span>
              </button>
            ))}
          </div>
          {(error ?? draw.error ?? interview.error) && (
            <p className="text-[13px] text-red-600">{(error ?? draw.error ?? interview.error)?.message}</p>
          )}
        </div>
        <div ref={composer} className="mx-auto w-full max-w-[720px] pt-4">
          <Composer
            value={text}
            onChange={setText}
            busy={draw.isPending}
            placeholder="Describe the face to start a new case… e.g. “a man in his thirties, round face, thin moustache”"
            onSubmit={(t) => draw.mutate(t)}
            chips={[
              { label: 'Witness interview', icon: <MessagesSquare size={14} />, onClick: () => interview.mutate() },
              ...(lastWithSketch ? [{ label: 'Open last case', icon: <PenLine size={14} />, onClick: () => navigate(`/cases/${lastWithSketch.id}`) }] : []),
            ]}
          />
        </div>
      </div>
      <CaseHistory cases={cases ?? []} loading={isPending} onNew={() => setNewOpen(true)} />
      <NewCaseDialog open={newOpen} onClose={() => setNewOpen(false)} />
    </div>
  )
}

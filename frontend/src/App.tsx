import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Home, LogOut, PenLine, Search, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { listCases, logout, me } from './api'
import CaseBar from './components/CaseBar'
import { CASE_PAGES } from './components/caseTabs'
import CommandPalette, { openPalette } from './components/CommandPalette'
import Splash from './components/Splash'
import TraceMark from './components/TraceMark'
import { recentCases, RECENT_EVENT, rememberVisit } from './lib/recent'
import AuditPage from './pages/AuditPage'
import CasesPage from './pages/CasesPage'
import CaseSheetPage from './pages/CaseSheetPage'
import DetailsPage from './pages/DetailsPage'
import FigurePage from './pages/FigurePage'
import InterviewPage from './pages/InterviewPage'
import InterviewRedirect from './pages/InterviewRedirect'
import LoginPage from './pages/LoginPage'
import StylesPage from './pages/StylesPage'
import WorkspacePage from './pages/WorkspacePage'
import type { User } from './types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: me })
}

const navItem = ({ isActive }: { isActive: boolean }) =>
  `flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 text-[13px] ${
    isActive ? 'bg-white font-medium text-ink shadow-[0_2px_10px_-4px_rgba(0,0,0,0.18)]' : 'text-body hover:bg-white/50 hover:text-ink'
  }`

// the last cases opened here, newest first; one click reopens the page you were on
function RecentCases({ caseId }: { caseId: number | null }) {
  const [recent, setRecent] = useState(recentCases)
  const cases = useQuery({ queryKey: ['cases'], queryFn: listCases, staleTime: 30_000 })
  useEffect(() => {
    const update = () => setRecent(recentCases())
    window.addEventListener(RECENT_EVENT, update)
    return () => window.removeEventListener(RECENT_EVENT, update)
  }, [])
  const byId = new Map((cases.data ?? []).map((c) => [c.id, c]))
  const shown = recent.filter((r) => byId.has(r.id)).slice(0, 5)
  if (!shown.length) return null
  return (
    <div className="flex flex-col gap-1">
      <div className="px-3 pb-1 text-[11px] uppercase tracking-[0.08em] text-faint">Recent cases</div>
      {shown.map((r) => {
        const c = byId.get(r.id)!
        return (
          <Link
            key={r.id}
            to={r.path}
            className={`flex items-center gap-2.5 rounded-[14px] px-2 py-1.5 text-[13px] ${
              r.id === caseId ? 'bg-white text-ink shadow-[0_2px_10px_-4px_rgba(0,0,0,0.18)]' : 'text-body hover:bg-white/50 hover:text-ink'
            }`}
          >
            {c.latest_image_url ? (
              <img src={c.latest_image_url} alt="" className="size-8 shrink-0 rounded-lg bg-cream object-cover object-top" />
            ) : (
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/70 text-faint">
                <PenLine size={14} />
              </span>
            )}
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="truncate">{c.title}</span>
              <span className="font-mono text-[10px] text-faint">{c.case_number}</span>
            </span>
          </Link>
        )
      })}
    </div>
  )
}

function Shell({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const caseMatch = useMatch('/cases/:id/*')
  const caseId = caseMatch && /^\d+$/.test(caseMatch.params.id ?? '') ? Number(caseMatch.params.id) : null
  const out = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })

  // remember where each case was left, and switch its pages with Alt+1…4
  useEffect(() => {
    if (caseId && !pathname.endsWith('/interview')) rememberVisit(caseId, pathname)
  }, [caseId, pathname])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const n = Number(e.key)
      if (!caseId || !e.altKey || !(n >= 1 && n <= CASE_PAGES.length)) return
      e.preventDefault()
      navigate(CASE_PAGES[n - 1].path(caseId))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [caseId, navigate])

  return (
    <div className="box-border h-screen p-4">
      <div className="grid h-full grid-cols-[210px_minmax(0,1fr)] overflow-hidden rounded-[28px] border border-ink/10 bg-white/60 shadow-[0_30px_80px_-40px_rgba(38,36,31,0.45)] backdrop-blur-xl">
        <aside className="flex min-h-0 flex-col gap-6 overflow-y-auto border-r border-black/[0.06] px-3 py-6">
          <Link to="/cases" className="px-3">
            <TraceMark />
          </Link>
          <nav className="flex flex-col gap-1">
            <NavLink end to="/cases" className={navItem}>
              <Home size={16} /> Home
            </NavLink>
            <button onClick={openPalette} className={navItem({ isActive: false })}>
              <Search size={16} /> Jump to…
              <kbd className="ml-auto rounded border border-line px-1 font-mono text-[10px] text-faint">Ctrl K</kbd>
            </button>
            {user.role === 'admin' && (
              <NavLink to="/audit" className={navItem}>
                <ShieldCheck size={16} /> Audit log
              </NavLink>
            )}
          </nav>
          <RecentCases caseId={caseId} />
          <div className="mt-auto flex flex-col gap-3 rounded-[18px] border border-ink/10 bg-ink/[0.05] p-3">
            <div className="flex items-center gap-2.5">
              <div className="grid size-9 place-items-center rounded-full bg-gradient-to-br from-[#efebe2] to-[#cfc7b7] text-sm font-semibold text-ink ring-2 ring-white">
                {user.username[0]?.toUpperCase()}
              </div>
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-medium">{user.username}</span>
                <span className="text-xs capitalize text-muted">{user.role}</span>
              </div>
            </div>
            <button
              onClick={() => out.mutate()}
              className="flex items-center justify-center gap-2 rounded-full bg-white/80 py-2 text-[13px] font-medium text-ink shadow-[0_2px_8px_-4px_rgba(0,0,0,0.3)] hover:bg-white"
            >
              <LogOut size={14} /> Log out
            </button>
          </div>
        </aside>
        <div className="flex min-h-0 min-w-0 flex-col gap-3 p-5">
          {caseId && <CaseBar caseId={caseId} />}
          {children}
        </div>
      </div>
      <CommandPalette admin={user.role === 'admin'} caseId={caseId} />
    </div>
  )
}

function Guard({ admin, children }: { admin?: boolean; children: ReactNode }) {
  const { data: user, isPending, isError } = useMe()
  if (isPending) return <p className="p-6 text-muted">Loading…</p>
  if (isError || !user) return <Navigate to="/login" replace />
  if (admin && user.role !== 'admin') return <Navigate to="/cases" replace />
  return <Shell user={user}>{children}</Shell>
}

export default function App() {
  return (
    <>
    <Splash />
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/cases"
        element={
          <Guard>
            <CasesPage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id"
        element={
          <Guard>
            <WorkspacePage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/details"
        element={
          <Guard>
            <DetailsPage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/styles"
        element={
          <Guard>
            <StylesPage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/figure"
        element={
          <Guard>
            <FigurePage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/sheet"
        element={
          <Guard>
            <CaseSheetPage />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/interview"
        element={
          <Guard>
            <InterviewRedirect />
          </Guard>
        }
      />
      <Route
        path="/cases/:id/interviews/:iid"
        element={
          <Guard>
            <InterviewPage />
          </Guard>
        }
      />
      <Route
        path="/audit"
        element={
          <Guard admin>
            <AuditPage />
          </Guard>
        }
      />
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
    </>
  )
}

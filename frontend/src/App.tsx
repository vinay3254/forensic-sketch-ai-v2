import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useMatch, useNavigate } from 'react-router-dom'
import { getCase, listCases, listInterviews, logout, me, startInterview } from './api'
import AuditPage from './pages/AuditPage'
import CasesPage from './pages/CasesPage'
import CaseSheetPage from './pages/CaseSheetPage'
import DetailsPage from './pages/DetailsPage'
import InterviewPage from './pages/InterviewPage'
import LoginPage from './pages/LoginPage'
import WorkspacePage from './pages/WorkspacePage'
import type { User } from './types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: me })
}

const navItem = ({ isActive }: { isActive: boolean }) =>
  `flex items-center justify-between rounded-[10px] px-2.5 py-[9px] text-sm ${
    isActive ? 'bg-cream font-medium text-ink' : 'text-side-text hover:bg-side hover:text-white'
  }`

// the open case's own pages: sketch, details, latest interview, sheet
function CaseNav({ caseId }: { caseId: number }) {
  const navigate = useNavigate()
  const c = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })
  const interviews = useQuery({ queryKey: ['interviews', caseId], queryFn: () => listInterviews(caseId) })
  const start = useMutation({
    mutationFn: () => startInterview(caseId),
    onSuccess: (iv) => navigate(`/cases/${caseId}/interviews/${iv.id}`),
  })
  const latest = interviews.data?.find((iv) => iv.status === 'draft') ?? interviews.data?.[0]
  return (
    <div className="flex flex-col gap-1">
      <div className="px-2.5 pb-1.5 text-[11px] uppercase tracking-[0.08em] text-faint">Open case</div>
      <div className="mb-1.5 flex flex-col gap-0.5 rounded-xl bg-side p-2.5">
        <div className="font-mono text-[11px] text-lilac">{c.data?.case.case_number ?? '…'}</div>
        <div className="truncate text-sm font-medium">{c.data?.case.title ?? ''}</div>
      </div>
      <NavLink end to={`/cases/${caseId}`} className={navItem}>
        Sketch workspace
      </NavLink>
      <NavLink to={`/cases/${caseId}/details`} className={navItem}>
        Person &amp; case details
      </NavLink>
      {latest ? (
        <NavLink to={`/cases/${caseId}/interviews/${latest.id}`} className={navItem}>
          Witness interview #{latest.id}
        </NavLink>
      ) : (
        <button onClick={() => start.mutate()} disabled={start.isPending} className={navItem({ isActive: false })}>
          Witness interview
          <span className="text-faint">+</span>
        </button>
      )}
      <NavLink to={`/cases/${caseId}/sheet`} className={navItem}>
        Case sheet
      </NavLink>
    </div>
  )
}

function Shell({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const caseMatch = useMatch('/cases/:id/*')
  const caseId = caseMatch ? Number(caseMatch.params.id) : null
  const cases = useQuery({ queryKey: ['cases'], queryFn: listCases, staleTime: 60_000 })
  const out = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })
  return (
    <div className="box-border grid h-screen grid-cols-[clamp(180px,20vw,232px)_minmax(0,1fr)] gap-3 overflow-hidden p-3">
      <aside className="box-border flex h-full min-h-0 flex-col gap-6 overflow-y-auto rounded-[22px] bg-ink px-3.5 py-5 text-[#ededea]">
        <Link to="/cases" className="flex items-center gap-2.5 px-2 text-[#ededea]">
          <div className="grid size-[30px] place-items-center rounded-[9px] bg-cream text-sm font-semibold text-ink">S</div>
          <div className="text-[15px] font-semibold tracking-[-0.01em]">Sketch Generator</div>
        </Link>
        <div className="flex flex-col gap-1">
          <div className="px-2.5 pb-1.5 text-[11px] uppercase tracking-[0.08em] text-faint">Workspace</div>
          <NavLink end to="/cases" className={navItem}>
            Cases
            <span className="font-mono text-[11px] text-faint">{cases.data?.length ?? ''}</span>
          </NavLink>
          {user.role === 'admin' && (
            <NavLink to="/audit" className={navItem}>
              Audit log
            </NavLink>
          )}
        </div>
        {caseId && !Number.isNaN(caseId) && <CaseNav key={caseId} caseId={caseId} />}
        <div className="mt-auto flex items-center gap-2.5 border-t border-side-line p-2.5">
          <div className="grid size-8 place-items-center rounded-full bg-[#3a3a40] text-xs font-medium">
            {user.username[0]?.toUpperCase()}
          </div>
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-[13px] font-medium">{user.username}</span>
            <span className="text-xs capitalize text-faint">{user.role}</span>
          </div>
          <button onClick={() => out.mutate()} title="Log out" className="ml-auto text-xs text-faint hover:text-white">
            Log out
          </button>
        </div>
      </aside>
      <main className="flex h-full min-h-0 min-w-0 flex-col gap-3">{children}</main>
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
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/cases" element={<Guard><CasesPage /></Guard>} />
      <Route path="/cases/:id" element={<Guard><WorkspacePage /></Guard>} />
      <Route path="/cases/:id/details" element={<Guard><DetailsPage /></Guard>} />
      <Route path="/cases/:id/sheet" element={<Guard><CaseSheetPage /></Guard>} />
      <Route path="/cases/:id/interviews/:iid" element={<Guard><InterviewPage /></Guard>} />
      <Route path="/audit" element={<Guard admin><AuditPage /></Guard>} />
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  )
}

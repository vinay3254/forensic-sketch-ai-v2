import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { logout, me } from './api'
import AuditPage from './pages/AuditPage'
import CasesPage from './pages/CasesPage'
import InterviewPage from './pages/InterviewPage'
import LoginPage from './pages/LoginPage'
import WorkspacePage from './pages/WorkspacePage'
import type { User } from './types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: me })
}

function Shell({ user, children }: { user: User; children: ReactNode }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const out = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate('/login')
    },
  })
  return (
    <div className="min-h-screen">
      <header className="flex items-center gap-6 bg-slate-900 px-6 py-3 text-white">
        <Link to="/cases" className="font-semibold">
          Sketch Generator
        </Link>
        <nav className="flex gap-4 text-sm text-slate-300">
          <Link to="/cases" className="hover:text-white">
            Cases
          </Link>
          {user.role === 'admin' && (
            <Link to="/audit" className="hover:text-white">
              Audit log
            </Link>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm">
          <span className="text-slate-300">
            {user.username} ({user.role})
          </span>
          <button onClick={() => out.mutate()} className="rounded bg-slate-700 px-3 py-1 hover:bg-slate-600">
            Log out
          </button>
        </div>
      </header>
      <main className="p-6">{children}</main>
    </div>
  )
}

function Guard({ admin, children }: { admin?: boolean; children: ReactNode }) {
  const { data: user, isPending, isError } = useMe()
  if (isPending) return <p className="p-6 text-slate-500">Loading…</p>
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
      <Route path="/cases/:id/interviews/:iid" element={<Guard><InterviewPage /></Guard>} />
      <Route path="/audit" element={<Guard admin><AuditPage /></Guard>} />
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  )
}

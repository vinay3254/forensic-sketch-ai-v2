import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FolderOpen, LogOut, ScrollText } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { logout, me } from './api'
import { initials, Logo, Spinner } from './components/ui'
import AuditPage from './pages/AuditPage'
import CasesPage from './pages/CasesPage'
import LoginPage from './pages/LoginPage'
import WorkspacePage from './pages/WorkspacePage'
import type { User } from './types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: me })
}

function NavItem({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === '/audit'}
      className={({ isActive }) =>
        `flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition ${
          isActive ? 'bg-white/10 text-white' : 'text-ink-300 hover:bg-white/5 hover:text-white'
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  )
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
      <header className="sticky top-0 z-30 border-b border-ink-800 bg-ink-950/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[90rem] items-center gap-6 px-6">
          <Link to="/cases" className="flex items-center gap-2.5">
            <Logo className="size-7" />
            <span className="text-sm font-semibold tracking-tight text-white">
              Sketch<span className="text-brass-400">Lab</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavItem to="/cases" icon={<FolderOpen className="size-4" />}>
              Cases
            </NavItem>
            {user.role === 'admin' && (
              <NavItem to="/audit" icon={<ScrollText className="size-4" />}>
                Audit log
              </NavItem>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-full bg-ink-700 text-xs font-semibold text-white ring-2 ring-ink-800">
                {initials(user.username)}
              </div>
              <div className="hidden leading-tight sm:block">
                <div className="text-sm font-medium text-white">{user.username}</div>
                <div className="text-[11px] capitalize text-ink-400">{user.role}</div>
              </div>
            </div>
            <div className="h-6 w-px bg-ink-700" />
            <button
              onClick={() => out.mutate()}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-300 transition hover:bg-white/5 hover:text-white"
            >
              <LogOut className="size-4" />
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[90rem] px-6 py-8">{children}</main>
    </div>
  )
}

function Guard({ admin, children }: { admin?: boolean; children: ReactNode }) {
  const { data: user, isPending, isError } = useMe()
  if (isPending) return <Spinner />
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
      <Route path="/audit" element={<Guard admin><AuditPage /></Guard>} />
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Fingerprint, History, Lock, PenLine, ShieldCheck, User as UserIcon } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api'
import { Button, ErrorBanner, Logo } from '../components/ui'

function Point({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-brass-400 ring-1 ring-white/10">{icon}</div>
      <div>
        <div className="text-sm font-medium text-white">{title}</div>
        <div className="text-sm text-ink-400">{body}</div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: (user) => {
      queryClient.clear()
      queryClient.setQueryData(['me'], user)
      navigate('/cases')
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <aside className="grid-lines relative hidden flex-col justify-between overflow-hidden bg-ink-950 p-12 lg:flex">
        <div className="absolute -right-32 -top-32 size-96 rounded-full bg-brass-500/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <Logo className="size-9" />
          <span className="text-lg font-semibold tracking-tight text-white">
            Sketch<span className="text-brass-400">Lab</span>
          </span>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight text-white">
            From a witness's words to a face you can circulate.
          </h1>
          <p className="mt-4 text-ink-400">
            Describe, refine by conversation, and export pencil sketches and realistic photos, with every access on record.
          </p>
          <div className="mt-10 space-y-5">
            <Point icon={<PenLine className="size-4" />} title="Forensic pencil sketches" body="Generated from the witness description, refined one feature at a time." />
            <Point icon={<History className="size-4" />} title="Full version history" body="Every change is a new version. Revert in one click." />
            <Point icon={<ShieldCheck className="size-4" />} title="Tamper-evident audit" body="Each action is hash-chained and verifiable by an administrator." />
          </div>
        </div>
        <p className="relative text-xs text-ink-500">Authorised personnel only. All activity is logged.</p>
      </aside>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Logo className="size-9" />
            <span className="text-lg font-semibold">
              Sketch<span className="text-brass-500">Lab</span>
            </span>
          </div>
          <div className="mb-2 flex size-11 items-center justify-center rounded-xl bg-white shadow-card ring-1 ring-paper-200">
            <Fingerprint className="size-5 text-brass-500" />
          </div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-ink-500">Use your department account to continue.</p>

          <div className="mt-8 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-700">Username</span>
              <div className="relative">
                <UserIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  className="h-11 w-full rounded-lg bg-white pl-9 pr-3 text-sm ring-1 ring-inset ring-paper-300 transition focus:outline-none focus:ring-2 focus:ring-brass-500"
                />
              </div>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-700">Password</span>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="h-11 w-full rounded-lg bg-white pl-9 pr-3 text-sm ring-1 ring-inset ring-paper-300 transition focus:outline-none focus:ring-2 focus:ring-brass-500"
                />
              </div>
            </label>
            {mutation.isError && <ErrorBanner message={mutation.error.message} />}
            <Button type="submit" className="h-11 w-full" disabled={!username || !password} loading={mutation.isPending}>
              {mutation.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

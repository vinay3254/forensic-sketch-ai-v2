import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, UserRound } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, signup } from '../api'
import TraceMark from '../components/TraceMark'
import type { User } from '../types'

type Mode = 'signin' | 'signup'
type Role = 'officer' | 'admin'

const field = 'mt-1 w-full rounded-xl border border-line bg-field px-3 py-2 text-[13px] outline-none focus:border-ink'

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('signin')
  const [role, setRole] = useState<Role>('officer')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [code, setCode] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const done = (user: User) => {
    queryClient.clear()
    queryClient.setQueryData(['me'], user)
    // admins land on their dashboard; investigators on their cases
    navigate(user.role === 'admin' ? '/dashboard' : '/cases')
  }
  const signIn = useMutation({ mutationFn: () => login(username, password), onSuccess: done })
  const create = useMutation({
    mutationFn: () => signup({ username, password, role, admin_code: role === 'admin' ? code : undefined }),
    onSuccess: done,
  })
  const busy = signIn.isPending || create.isPending
  const error = mode === 'signin' ? signIn.error : create.error
  const mismatch = mode === 'signup' && confirm !== '' && confirm !== password
  const ready =
    mode === 'signin'
      ? username && password
      : /^[A-Za-z0-9_.-]{3,32}$/.test(username) && password.length >= 8 && confirm === password && (role === 'officer' || code)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (mode === 'signin') signIn.mutate()
    else create.mutate()
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-5 p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-[24px] bg-white p-6 shadow-[0_30px_80px_-40px_rgba(38,36,31,0.45)]">
        <h1 className="flex flex-col items-center gap-1 pb-1">
          <TraceMark size="lg" />
          <span className="text-xs text-muted">Forensic sketch workspace</span>
        </h1>
        <div className="flex rounded-full bg-field p-1 text-[13px]" role="tablist">
          {(['signin', 'signup'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-full py-1.5 ${mode === m ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}
            >
              {m === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        {mode === 'signup' && (
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Account type">
            {(
              [
                ['officer', 'Investigator', 'Draw sketches, interview witnesses, work cases', <UserRound key="i" size={18} />],
                ['admin', 'Admin', 'Oversee investigators, sessions and logs', <ShieldCheck key="a" size={18} />],
              ] as const
            ).map(([r, label, hint, icon]) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={role === r}
                onClick={() => setRole(r)}
                className={`flex flex-col gap-1 rounded-2xl border p-3 text-left ${role === r ? 'border-ink bg-field' : 'border-line hover:border-ink/40'}`}
              >
                <span className="flex items-center gap-1.5 text-[13px] font-medium text-ink">
                  {icon}
                  {label}
                </span>
                <span className="text-[11px] leading-snug text-muted">{hint}</span>
              </button>
            ))}
          </div>
        )}

        <label className="block text-[13px]">
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className={field} />
          {mode === 'signup' && <span className="mt-1 block text-[11px] text-muted">3–32 letters, numbers, dot, dash or underscore</span>}
        </label>
        <label className="block text-[13px]">
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} className={field} />
          {mode === 'signup' && <span className="mt-1 block text-[11px] text-muted">At least 8 characters</span>}
        </label>
        {mode === 'signup' && (
          <label className="block text-[13px]">
            Confirm password
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" className={field} />
            {mismatch && <span className="mt-1 block text-[11px] text-accent">The passwords don't match</span>}
          </label>
        )}
        {mode === 'signup' && role === 'admin' && (
          <label className="block text-[13px]">
            Admin code
            <input type="password" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" className={field} />
            <span className="mt-1 block text-[11px] text-muted">Admins can see every investigator's activity, so creating one needs the code from your system administrator.</span>
          </label>
        )}
        {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{error.message}</p>}
        <button type="submit" disabled={!ready || busy} className="w-full rounded-full bg-ink py-2.5 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50">
          {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : role === 'admin' ? 'Create admin account' : 'Create investigator account'}
        </button>
      </form>
      <p className="max-w-sm text-center text-[12px] font-medium leading-relaxed text-muted">
        <span className="font-semibold text-ink">Disclaimer.</span> TRACE is an investigative aid. Its sketches, 3D figures,
        translations and record matches are produced with AI from witness accounts and are not proof of anyone's
        identity. All output should be reviewed by a trained officer and corroborated by independent evidence.
      </p>
    </div>
  )
}

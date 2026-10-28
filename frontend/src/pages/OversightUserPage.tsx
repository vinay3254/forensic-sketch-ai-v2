import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { auditList, oversight, sessionTimeline, userCases, userSessions } from '../api'
import PageHeader from '../components/PageHeader'
import type { SessionEnd, UserSession } from '../types'
import { when } from './OversightPage'

const ENDED: Record<SessionEnd, string> = {
  logout: 'Logged out',
  new_login: 'Logged in again without logging out',
  expired: 'Expired without logging out',
  active: 'Still logged in',
}

const time = (iso: string) => new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })
const summary = (by: Record<string, number>) =>
  Object.entries(by)
    .filter(([a]) => a !== 'login' && a !== 'logout')
    .sort((a, b) => b[1] - a[1])
    .map(([a, n]) => `${a.replace(/_/g, ' ')} ×${n}`)
    .join(', ')

type Row = { id: number; ts: string; action: string; case_id: number | null; version_id: number | null; detail: Record<string, unknown>; username?: string | null }

function Timeline({ rows }: { rows: Row[] }) {
  return (
    <ol className="mt-2 space-y-1 border-l-2 border-line pl-4 text-[13px]">
      {rows.map((r) => (
        <li key={r.id} className="grid grid-cols-[150px_150px_minmax(0,1fr)] gap-2">
          <span className="font-mono text-xs text-muted">{time(r.ts)}</span>
          <span className={r.action === 'access_denied' || r.action === 'login_failed' ? 'text-accent' : 'text-ink'}>
            {r.action.replace(/_/g, ' ')}
          </span>
          <span className="truncate text-xs text-muted" title={JSON.stringify(r.detail)}>
            {r.username && `${r.username} · `}
            {r.case_id && `case #${r.case_id} `}
            {r.version_id && `v${r.version_id} `}
            {Object.keys(r.detail).length > 0 && JSON.stringify(r.detail)}
          </span>
        </li>
      ))}
    </ol>
  )
}

function SessionRow({ uid, s }: { uid: number; s: UserSession }) {
  const [open, setOpen] = useState(false)
  const rows = useQuery({ queryKey: ['session', uid, s.id], queryFn: () => sessionTimeline(uid, s.id), enabled: open })
  return (
    <li className="rounded-2xl border border-line p-3">
      <button onClick={() => setOpen(!open)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 text-left text-[13px]">
        <span className="font-medium text-ink">{when(s.start)}</span>
        <span className="text-muted">→ {s.end ? when(s.end) : 'now'}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${s.end_reason === 'active' ? 'bg-green-100 text-green-800' : s.end_reason === 'logout' ? 'bg-field text-muted' : 'bg-amber-100 text-amber-800'}`}>
          {ENDED[s.end_reason]}
        </span>
        <span className="text-xs text-muted">{s.actions} actions · {s.cases.length} cases · {s.ip ?? 'unknown IP'}</span>
        <span className="ml-auto text-xs text-link">{open ? 'Hide' : 'Show everything'}</span>
      </button>
      {s.cases.length > 0 && (
        <p className="mt-1 text-xs text-body">
          Cases: {s.cases.map((c) => `${c.case_number} ${c.title}`).join(' · ')}
        </p>
      )}
      {summary(s.by_action) && <p className="mt-0.5 text-xs text-muted">{summary(s.by_action)}</p>}
      {open && (rows.data ? <Timeline rows={rows.data} /> : <p className="mt-2 text-xs text-muted">Loading…</p>)}
    </li>
  )
}

function CaseRow({ c }: { c: { case_id: number; case_number: string | null; title: string; owned: boolean; first: string; last: string; actions: number; by_action: Record<string, number> } }) {
  const [open, setOpen] = useState(false)
  // everything anyone did in this case, not only this investigator
  const log = useQuery({ queryKey: ['case-log', c.case_id], queryFn: () => auditList({ case_id: c.case_id, page: 1, page_size: 200 }), enabled: open })
  return (
    <li className="rounded-2xl border border-line p-3 text-[13px]">
      <button onClick={() => setOpen(!open)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 text-left">
        <span className="font-mono text-xs text-muted">{c.case_number}</span>
        <span className="font-medium text-ink">{c.title}</span>
        {c.owned && <span className="rounded bg-field px-1.5 py-0.5 text-[11px]">created by them</span>}
        <span className="text-xs text-muted">
          {when(c.first)} → {when(c.last)} · {c.actions} actions
        </span>
        <span className="ml-auto text-xs text-link">{open ? 'Hide' : 'Full case log'}</span>
      </button>
      <p className="mt-0.5 text-xs text-muted">{summary(c.by_action)}</p>
      {open && (log.data ? <Timeline rows={[...log.data.items].reverse()} /> : <p className="mt-2 text-xs text-muted">{log.error?.message ?? 'Loading…'}</p>)}
    </li>
  )
}

export default function OversightUserPage() {
  const uid = Number(useParams().uid)
  const [tab, setTab] = useState<'sessions' | 'cases'>('sessions')
  const sessions = useQuery({ queryKey: ['sessions', uid], queryFn: () => userSessions(uid) })
  const cases = useQuery({ queryKey: ['user-cases', uid], queryFn: () => userCases(uid), enabled: tab === 'cases' })
  const people = useQuery({ queryKey: ['oversight'], queryFn: oversight })
  const p = [...(people.data?.team ?? []), ...(people.data?.admins ?? [])].find((x) => x.user_id === uid)
  const error = sessions.error ?? cases.error
  return (
    <>
      <PageHeader crumbs={[{ label: 'Oversight', to: '/oversight' }]} title={p ? p.username : `User #${uid}`} />
      {p && (
        <p className="-mt-1 shrink-0 text-[13px] text-muted">
          {p.role === 'admin' ? 'Admin' : 'Investigator'}
          {p.role !== 'admin' && ` · overseen by ${p.supervisor ?? 'any admin'}`} · {p.logins} logins, {p.logouts} logouts, {p.failed_logins} failed · last seen {when(p.last_seen)}
          {p.active_now && ' · logged in now'}
        </p>
      )}
      <Link to="/oversight" className="-mt-1 shrink-0 text-[13px] text-link hover:text-ink">
        ← All investigators
      </Link>
      <div className="flex shrink-0 gap-2">
        {(['sessions', 'cases'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-4 py-2 text-[13px] ${tab === t ? 'bg-ink text-white' : 'bg-white text-ink'}`}>
            {t === 'sessions' ? `Sessions${sessions.data ? ` (${sessions.data.length})` : ''}` : 'Cases handled'}
          </button>
        ))}
      </div>
      {error && <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error.message}</p>}
      <section className="min-h-0 flex-1 overflow-y-auto rounded-[22px] bg-white p-5">
        {tab === 'sessions' &&
          (sessions.data ? (
            sessions.data.length ? (
              <ul className="space-y-2">
                {sessions.data.map((s) => (
                  <SessionRow key={s.id} uid={uid} s={s} />
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-muted">No sessions recorded.</p>
            )
          ) : (
            !error && <p className="text-muted">Loading…</p>
          ))}
        {tab === 'cases' &&
          (cases.data ? (
            cases.data.length ? (
              <ul className="space-y-2">
                {cases.data.map((c) => (
                  <CaseRow key={c.case_id} c={c} />
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-muted">No cases handled.</p>
            )
          ) : (
            !error && <p className="text-muted">Loading…</p>
          ))}
      </section>
    </>
  )
}

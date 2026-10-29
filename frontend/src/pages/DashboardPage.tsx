import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Brush, FolderOpen, LogIn, MessagesSquare, UserRound, UsersRound } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { dashboard } from '../api'
import { useMe } from '../App'
import { Legend, PersonBars, SERIES, SESSION_COLOR, SESSION_LABEL, SessionTimeline, Sparkline } from '../components/charts'
import PageHeader from '../components/PageHeader'
import type { Dashboard, LiveTask, WorkGroup } from '../types'

const GROUPS: WorkGroup[] = ['sketch', 'interview', 'casework', 'account']
const GROUP_LABEL: Record<WorkGroup, string> = {
  sketch: 'Sketch & 3D',
  interview: 'Interviews',
  casework: 'Case work',
  account: 'Sign-in & account',
}
const GROUP_ICON: Record<WorkGroup, ReactNode> = {
  sketch: <Brush size={13} />,
  interview: <MessagesSquare size={13} />,
  casework: <FolderOpen size={13} />,
  account: <LogIn size={13} />,
}
const DAYS = 14

const ago = (iso: string | null) => {
  if (!iso) return 'never'
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m} min ago`
  if (m < 1440) return `${Math.round(m / 60)} h ago`
  return `${Math.round(m / 1440)} d ago`
}

function Tile({ label, value, icon, tone }: { label: string; value: number; icon: ReactNode; tone?: 'alert' | 'live' }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white px-4 py-3">
      <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${tone === 'alert' && value ? 'bg-accent-soft/60 text-accent' : tone === 'live' ? 'bg-[#1baf7a]/15 text-[#13805a]' : 'bg-field text-ink'}`}>{icon}</span>
      <div className="min-w-0">
        <p className="truncate text-xs text-muted">{label}</p>
        <p className={`text-xl font-semibold ${tone === 'alert' && value ? 'text-accent' : 'text-ink'}`}>{value}</p>
      </div>
    </div>
  )
}

function Card({ title, sub, actions, children, className = '' }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`flex min-w-0 flex-col gap-3 rounded-[22px] bg-white p-5 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          {sub && <p className="text-xs text-muted">{sub}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}

// re-render every second so "23 s" and "2 min ago" stay true
function useNow() {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  return now
}

const elapsed = (iso: string, now: number) => {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}

// refresh the moment the server says something changed (server-sent events), with a slow poll as backup
function useLive() {
  const queryClient = useQueryClient()
  const [live, setLive] = useState(false)
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    const es = new EventSource('/api/admin/live')
    es.onopen = () => setLive(true)
    es.onerror = () => setLive(false)
    es.onmessage = () => {
      clearTimeout(timer)
      timer = setTimeout(() => queryClient.invalidateQueries({ queryKey: ['dashboard'] }), 250)
    }
    return () => {
      clearTimeout(timer)
      es.close()
    }
  }, [queryClient])
  return live
}

function Doing({ t, now }: { t: LiveTask; now: number }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 text-xs text-ink">
      <span className="size-3 shrink-0 animate-spin rounded-full border-2 border-line border-t-accent" />
      <span className="truncate">
        {t.label}
        {t.case_number && <span className="text-muted"> · {t.case_number}</span>}
      </span>
      <span className="shrink-0 font-mono text-[11px] text-muted">{elapsed(t.started, now)}</span>
    </span>
  )
}

const STATUS_TEXT: Record<Dashboard['people'][number]['status'], string> = {
  active: 'Active now',
  idle: 'Signed in, idle',
  signed_out: 'Signed out',
  never: 'Never signed in',
}

type Person = Dashboard['people'][number]


function PersonCard({ p, now, onOpen }: { p: Person; now: number; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="flex items-center gap-3 rounded-2xl border border-line-soft p-3 text-left hover:border-ink/30 hover:bg-field/60">
      <span className="relative grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#efebe2] to-[#cfc7b7] font-semibold text-ink">
        {p.username[0]?.toUpperCase()}
        {(p.status === 'active' || p.status === 'idle') && (
          <span className="absolute -right-0.5 -top-0.5 size-3 rounded-full border-2 border-white" style={{ background: SESSION_COLOR[p.status] }} title={STATUS_TEXT[p.status]} />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium text-ink">{p.username}</span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${p.status === 'active' ? 'bg-[#1baf7a]/15 text-[#13805a]' : p.status === 'idle' ? 'bg-[#8fd6b8]/25 text-[#2f7f60]' : 'bg-field text-muted'}`}
          >
            {STATUS_TEXT[p.status]}
          </span>
        </span>
        <span className="block truncate text-xs text-muted">
          {p.status === 'active' || p.status === 'idle'
            ? `${p.page ? `On ${p.page}` : 'Open'} · last active ${ago(p.last_seen)}`
            : `Last seen ${ago(p.last_seen)}`}
          {p.supervisor ? ` · under ${p.supervisor}` : ''}
        </span>
        {p.doing.map((t) => (
          <Doing key={t.started + t.label} t={t} now={now} />
        ))}
        <span className="mt-1 flex gap-3 text-xs text-body">
          <span><b className="font-semibold text-ink">{p.cases}</b> cases</span>
          <span><b className="font-semibold text-ink">{p.sessions}</b> sessions</span>
          {p.role !== 'admin' && <span><b className="font-semibold text-ink">{p.sketches}</b> sketches</span>}
        </span>
      </span>
      <span className="hidden shrink-0 flex-col items-end sm:flex" title={`Actions per day over ${DAYS} days`}>
        <Sparkline values={p.daily_actions} />
        <span className="text-[10px] text-faint">{p.actions} actions</span>
      </span>
    </button>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const live = useLive()
  const now = useNow()
  const { data, error, isPending, dataUpdatedAt } = useQuery({
    queryKey: ['dashboard', DAYS],
    queryFn: () => dashboard(DAYS),
    refetchInterval: 60_000, // backup only; the live stream drives refreshes
    placeholderData: (p) => p,
  })
  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error || !data) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error?.message}</p>

  const t = data.totals
  const team = data.people.filter((p) => p.role !== 'admin')
  const admins = data.people.filter((p) => p.role === 'admin')
  const openUser = (id: number) => navigate(`/oversight/users/${id}`)
  const hour = new Date().getHours()

  return (
    <>
      <PageHeader
        crumbs={[{ label: 'Dashboard' }]}
        title={`Good ${hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'}, ${me?.username ?? 'admin'}`}
        actions={
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs text-body" title="Updates the moment anything happens">
            <span className={`size-2 rounded-full ${live ? 'animate-pulse bg-[#1baf7a]' : 'bg-ghost'}`} />
            {live ? 'Live' : 'Reconnecting…'} · updated {Math.max(0, Math.round((now - dataUpdatedAt) / 1000))} s ago
          </span>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-2">
        <div className="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-3">
          <Tile label="Investigators" value={t.investigators} icon={<UsersRound size={17} />} />
          <Tile label={`Active now${t.idle ? ` · ${t.idle} idle` : ''}`} value={t.online} icon={<span className="size-2.5 animate-pulse rounded-full bg-[#1baf7a]" />} tone="live" />
          <Tile label={`Cases worked · last ${DAYS} days`} value={t.cases} icon={<FolderOpen size={17} />} />
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <Card title="Admins" sub="Admins' own activity is logged too. Click anyone for their sessions and cases.">
            <div className="flex flex-col gap-2">
              {admins.map((p) => (
                <PersonCard key={p.user_id} p={p} now={now} onOpen={() => openUser(p.user_id)} />
              ))}
            </div>
          </Card>
          <Card title="Investigators" sub="Click anyone to see their sessions and the cases they handled.">
            <div className="flex flex-col gap-2">
              {team.length === 0 && <p className="text-[13px] text-muted">No investigators assigned to you yet.</p>}
              {team.map((p) => (
                <PersonCard key={p.user_id} p={p} now={now} onOpen={() => openUser(p.user_id)} />
              ))}
            </div>
          </Card>
        </div>

        <Card title="Who was logged in, and when" sub="Each bar is one session, from sign-in to sign-out. Click a name or a bar for the full log.">
          <Legend items={(['active', 'idle', 'logout', 'new_login'] as const).map((k) => ({ label: SESSION_LABEL[k], color: SESSION_COLOR[k] }))} />
          <SessionTimeline sessions={data.sessions} people={data.people} from={new Date(data.daily[0].date + 'T00:00:00')} onPick={openUser} />
        </Card>

        <Card title="Cases worked per person" sub={`Distinct cases each person touched in the last ${DAYS} days. Click a bar for their cases.`}>
          <PersonBars unit="cases" items={[...data.people].sort((a, b) => b.cases - a.cases).map((p) => ({ label: p.username, value: p.cases, onClick: () => openUser(p.user_id) }))} />
        </Card>

        <Card
          title="Latest activity"
          sub="Work being done now, then the 20 most recent logged actions"
          actions={
            <Link to="/audit" className="text-xs text-link hover:text-ink">
              Full audit log →
            </Link>
          }
        >
          <Legend items={GROUPS.map((g, i) => ({ label: GROUP_LABEL[g], color: SERIES[i] }))} />
          {data.in_progress.length > 0 && (
            <div className="flex flex-col gap-1.5 rounded-2xl border border-accent-soft bg-accent-soft/15 p-3">
              <p className="text-xs font-medium text-accent">In progress right now</p>
              {data.in_progress.map((t) => (
                <span key={t.user_id + t.started} className="flex items-center gap-2 text-[13px]">
                  <span className="inline-flex shrink-0 items-center gap-1 font-medium text-ink">
                    <UserRound size={12} className="text-faint" />
                    {t.username}
                  </span>
                  <Doing t={t} now={now} />
                </span>
              ))}
            </div>
          )}
          <ol className="grid gap-x-6 gap-y-1.5 md:grid-cols-2">
            {data.recent.map((r) => (
              <li key={r.id} className="flex min-w-0 items-center gap-2 text-[13px]">
                <span className="grid size-6 shrink-0 place-items-center rounded-lg text-white" style={{ background: SERIES[GROUPS.indexOf(r.group)] }} title={GROUP_LABEL[r.group]}>
                  {GROUP_ICON[r.group]}
                </span>
                <span className="w-16 shrink-0 text-xs text-muted">{ago(r.ts)}</span>
                <span className="inline-flex shrink-0 items-center gap-1 font-medium text-ink">
                  <UserRound size={12} className="text-faint" />
                  {r.username}
                </span>
                <span className="min-w-0 truncate text-body">
                  {r.action.replace(/_/g, ' ')}
                  {r.case_number && <span className="text-muted"> · {r.case_number} {r.case_title}</span>}
                </span>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </>
  )
}

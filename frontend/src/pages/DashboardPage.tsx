import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Brush, FolderOpen, LogIn, MessagesSquare, ShieldAlert, UserRound, UsersRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { dashboard } from '../api'
import { useMe } from '../App'
import { Legend, PersonBars, SERIES, SessionTimeline, SignIns, Sparkline, StackedDays } from '../components/charts'
import PageHeader from '../components/PageHeader'
import type { WorkGroup } from '../types'

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
const RANGES = [7, 14, 30]

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

export default function DashboardPage() {
  const [days, setDays] = useState(14)
  const [table, setTable] = useState(false)
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data, error, isPending } = useQuery({ queryKey: ['dashboard', days], queryFn: () => dashboard(days), refetchInterval: 30_000, placeholderData: (p) => p })
  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error || !data) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error?.message}</p>

  const t = data.totals
  const team = data.people.filter((p) => p.role !== 'admin')
  const admins = data.people.filter((p) => p.role === 'admin')
  const openUser = (id: number) => navigate(`/oversight/users/${id}`)
  const from = new Date(data.daily[0].date + 'T00:00:00')
  const alerts = data.people.filter((p) => p.failed_logins || p.denied)

  return (
    <>
      <PageHeader
        crumbs={[{ label: 'Dashboard' }]}
        title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${me?.username ?? 'admin'}`}
        actions={
          <div className="flex rounded-full bg-white p-0.5 text-xs" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <button key={r} onClick={() => setDays(r)} aria-pressed={days === r} className={`rounded-full px-3 py-1.5 ${days === r ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>
                {r} days
              </button>
            ))}
          </div>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-2">
        <div className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Tile label="Investigators" value={t.investigators} icon={<UsersRound size={17} />} />
          <Tile label="Logged in now" value={t.online} icon={<span className="size-2.5 animate-pulse rounded-full bg-[#1baf7a]" />} tone="live" />
          <Tile label={`Sessions · ${days} d`} value={t.sessions} icon={<LogIn size={17} />} />
          <Tile label={`Cases worked · ${days} d`} value={t.cases} icon={<FolderOpen size={17} />} />
          <Tile label={`Sketches made · ${days} d`} value={t.sketches} icon={<Brush size={17} />} />
          <Tile label="Failed logins + denials" value={t.failed_logins + t.denied} icon={<ShieldAlert size={17} />} tone="alert" />
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Card
            title="What the team did, day by day"
            sub="Every logged action, grouped by kind of work. Hover a day for the numbers."
            actions={
              <button onClick={() => setTable(!table)} className="rounded-full border border-line px-3 py-1 text-xs text-body hover:border-ink">
                {table ? 'Show chart' : 'Show as table'}
              </button>
            }
          >
            <Legend items={GROUPS.map((g, i) => ({ label: GROUP_LABEL[g], color: SERIES[i] }))} />
            {table ? (
              <div className="max-h-64 overflow-auto">
                <table className="w-full text-right text-xs">
                  <thead className="sticky top-0 bg-white text-muted">
                    <tr>
                      <th className="py-1 text-left font-medium">Day</th>
                      {GROUPS.map((g) => (
                        <th key={g} className="py-1 font-medium">{GROUP_LABEL[g]}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.daily.map((d) => (
                      <tr key={d.date} className="border-t border-line-soft">
                        <td className="py-1 text-left font-mono">{d.date}</td>
                        {GROUPS.map((g) => (
                          <td key={g} className="py-1 font-mono">{d.groups[g]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <StackedDays days={data.daily.map((d) => ({ date: d.date, values: d.groups }))} keys={GROUPS} labels={GROUP_LABEL} />
            )}
          </Card>
          <Card title="Sign-ins" sub="Successful sign-ins per day; red dots are failed attempts.">
            <Legend
              items={[
                { label: 'Sign-ins', color: '#3d3a34' },
                { label: 'Failed sign-ins', color: '#b0442c', note: <AlertTriangle size={11} className="text-accent" /> },
              ]}
            />
            <SignIns days={data.daily} />
            {alerts.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                {alerts.map((p) => (
                  <button key={p.user_id} onClick={() => openUser(p.user_id)} className="flex items-center gap-2 rounded-xl bg-accent-soft/30 px-3 py-2 text-left text-[13px] hover:bg-accent-soft/50">
                    <AlertTriangle size={14} className="shrink-0 text-accent" />
                    <span className="font-medium text-ink">{p.username}</span>
                    <span className="text-body">
                      {[p.failed_logins && `${p.failed_logins} failed sign-in${p.failed_logins > 1 ? 's' : ''}`, p.denied && `${p.denied} denied access`].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="rounded-xl bg-field px-3 py-2 text-[13px] text-body">No failed sign-ins or denied access in this period.</p>
            )}
          </Card>
        </div>

        <Card title="Who was logged in, and when" sub="Each bar is one session, from sign-in to sign-out. Click a name or a bar for the full log.">
          <Legend
            items={[
              { label: 'Logged in now', color: '#1baf7a' },
              { label: 'Signed out', color: '#2a78d6' },
              { label: 'Left without signing out', color: '#958f83' },
            ]}
          />
          <SessionTimeline sessions={data.sessions} people={data.people} from={from} onPick={openUser} />
        </Card>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Card title="Investigators" sub="Click anyone to see their sessions and the cases they handled.">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {team.length === 0 && <p className="text-[13px] text-muted">No investigators assigned to you yet.</p>}
              {team.map((p) => (
                <button key={p.user_id} onClick={() => openUser(p.user_id)} className="flex items-center gap-3 rounded-2xl border border-line-soft p-3 text-left hover:border-ink/30 hover:bg-field/60">
                  <span className="relative grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#efebe2] to-[#cfc7b7] font-semibold text-ink">
                    {p.username[0]?.toUpperCase()}
                    {p.online && <span className="absolute -right-0.5 -top-0.5 size-3 rounded-full border-2 border-white bg-[#1baf7a]" title="Logged in now" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-ink">{p.username}</span>
                    <span className="block truncate text-xs text-muted">
                      {p.online ? 'Logged in now' : `Last seen ${ago(p.last_seen)}`}
                      {p.supervisor ? ` · under ${p.supervisor}` : ''}
                    </span>
                    <span className="mt-1 flex gap-3 text-xs text-body">
                      <span><b className="font-semibold text-ink">{p.cases}</b> cases</span>
                      <span><b className="font-semibold text-ink">{p.sessions}</b> sessions</span>
                      <span><b className="font-semibold text-ink">{p.sketches}</b> sketches</span>
                    </span>
                  </span>
                  <span className="hidden shrink-0 flex-col items-end sm:flex" title={`Actions per day over ${days} days`}>
                    <Sparkline values={p.daily_actions} />
                    <span className="text-[10px] text-faint">{p.actions} actions</span>
                  </span>
                </button>
              ))}
            </div>
          </Card>
          <div className="flex min-w-0 flex-col gap-3">
            <Card title="Cases worked per person" sub={`Distinct cases touched in ${days} days`}>
              <PersonBars unit="cases" items={[...data.people].sort((a, b) => b.cases - a.cases).map((p) => ({ label: p.username, value: p.cases, onClick: () => openUser(p.user_id) }))} />
            </Card>
            <Card title="Admins" sub="Admins' own activity is logged too.">
              <div className="flex flex-wrap gap-2">
                {admins.map((p) => (
                  <button key={p.user_id} onClick={() => openUser(p.user_id)} className="inline-flex items-center gap-2 rounded-full bg-field px-3 py-1.5 text-[13px] hover:bg-tint">
                    <span className={`size-2 rounded-full ${p.online ? 'bg-[#1baf7a]' : 'bg-ghost'}`} />
                    {p.username}
                    <span className="text-xs text-muted">{p.actions}</span>
                  </button>
                ))}
              </div>
            </Card>
          </div>
        </div>

        <Card
          title="Latest activity"
          sub="The 20 most recent logged actions"
          actions={
            <Link to="/audit" className="text-xs text-link hover:text-ink">
              Full audit log →
            </Link>
          }
        >
          <ol className="grid gap-x-6 gap-y-1.5 md:grid-cols-2">
            {data.recent.map((r) => (
              <li key={r.id} className="flex items-center gap-2 text-[13px]">
                <span className="grid size-6 shrink-0 place-items-center rounded-lg text-white" style={{ background: SERIES[GROUPS.indexOf(r.group)] }} title={GROUP_LABEL[r.group]}>
                  {GROUP_ICON[r.group]}
                </span>
                <span className="w-16 shrink-0 text-xs text-muted">{ago(r.ts)}</span>
                <span className="inline-flex shrink-0 items-center gap-1 font-medium text-ink">
                  <UserRound size={12} className="text-faint" />
                  {r.username}
                </span>
                <span className="truncate text-body">
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

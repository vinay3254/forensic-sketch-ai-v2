import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { assignSupervisor, oversight } from '../api'
import { useMe } from '../App'
import PageHeader from '../components/PageHeader'
import type { Oversight, OversightPerson } from '../types'

export const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—')

function Status({ p }: { p: OversightPerson }) {
  return p.active_now ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">
      <span className="size-1.5 rounded-full bg-green-600" /> Logged in
    </span>
  ) : (
    <span className="rounded-full bg-field px-2 py-0.5 text-xs text-muted">Offline</span>
  )
}

function PeopleTable({ people, data, assignable }: { people: OversightPerson[]; data: Oversight; assignable: boolean }) {
  const queryClient = useQueryClient()
  const assign = useMutation({
    mutationFn: ({ id, admin }: { id: number; admin: number | null }) => assignSupervisor(id, admin),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['oversight'] }),
  })
  if (people.length === 0) return <p className="p-4 text-[13px] text-muted">Nobody here yet.</p>
  return (
    <div className="overflow-x-auto">
      {assign.error && <p className="mb-2 text-[13px] text-red-700">{assign.error.message}</p>}
      <table className="w-full text-left text-[13px]">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">Name</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            {assignable && <th className="py-2 pr-3 font-medium">Overseen by</th>}
            <th className="py-2 pr-3 font-medium">Last login</th>
            <th className="py-2 pr-3 font-medium">Last logout</th>
            <th className="py-2 pr-3 text-right font-medium">Logins</th>
            <th className="py-2 pr-3 text-right font-medium">Sessions</th>
            <th className="py-2 pr-3 text-right font-medium">Cases</th>
            <th className="py-2 pr-3 text-right font-medium">Actions</th>
            <th className="py-2 pr-3 text-right font-medium">Failed logins</th>
            <th className="py-2 text-right font-medium">Denied</th>
          </tr>
        </thead>
        <tbody>
          {people.map((p) => (
            <tr key={p.user_id} className="border-b border-line-soft hover:bg-field/60">
              <td className="py-2 pr-3">
                <Link to={`/oversight/users/${p.user_id}`} className="font-medium text-ink hover:text-accent">
                  {p.username}
                </Link>
              </td>
              <td className="py-2 pr-3">
                <Status p={p} />
              </td>
              {assignable && (
                <td className="py-2 pr-3">
                  <select
                    value={p.supervisor_id ?? ''}
                    disabled={assign.isPending}
                    onChange={(e) => assign.mutate({ id: p.user_id, admin: e.target.value ? Number(e.target.value) : null })}
                    className="rounded-full border border-line bg-white px-2 py-1 text-xs"
                    aria-label={`Admin overseeing ${p.username}`}
                  >
                    <option value="">Any admin</option>
                    {data.admin_choices.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.username}
                      </option>
                    ))}
                  </select>
                </td>
              )}
              <td className="py-2 pr-3 text-xs">{when(p.last_login)}</td>
              <td className="py-2 pr-3 text-xs">{when(p.last_logout)}</td>
              <td className="py-2 pr-3 text-right">{p.logins}</td>
              <td className="py-2 pr-3 text-right">{p.sessions}</td>
              <td className="py-2 pr-3 text-right">{p.cases}</td>
              <td className="py-2 pr-3 text-right">{p.actions}</td>
              <td className={`py-2 pr-3 text-right ${p.failed_logins ? 'text-accent' : ''}`}>{p.failed_logins}</td>
              <td className={`py-2 text-right ${p.denied ? 'text-accent' : ''}`}>{p.denied}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function OversightPage() {
  const { data: user } = useMe()
  const { data, error, isPending } = useQuery({ queryKey: ['oversight'], queryFn: oversight, refetchInterval: 30_000 })
  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error || !data) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error?.message}</p>
  const t = data.totals
  return (
    <>
      <PageHeader crumbs={[{ label: 'Oversight' }]} title="Investigator oversight" />
      <p className="-mt-1 shrink-0 text-[13px] text-muted">
        Investigators assigned to you ({user?.username}), plus anyone not yet assigned to an admin, and every admin. Built from the tamper-evident audit log; refreshes every 30 s.
      </p>
      <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-6">
        {[
          ['Investigators', t.investigators],
          ['Assigned to you', t.mine],
          ['Not assigned', t.unassigned],
          ['Logged in now', t.active_now],
          ['Logins', t.logins],
          ['Failed logins', t.failed_logins],
        ].map(([k, n]) => (
          <div key={k} className="rounded-2xl bg-white px-4 py-3">
            <p className="text-xs text-muted">{k}</p>
            <p className="text-xl font-semibold text-ink">{n}</p>
          </div>
        ))}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        <section className="rounded-[22px] bg-white p-5">
          <h2 className="mb-2 text-[15px] font-semibold">Investigators</h2>
          <PeopleTable people={data.team} data={data} assignable />
        </section>
        <section className="rounded-[22px] bg-white p-5">
          <h2 className="mb-2 text-[15px] font-semibold">Admins</h2>
          <PeopleTable people={data.admins} data={data} assignable={false} />
        </section>
      </div>
    </>
  )
}

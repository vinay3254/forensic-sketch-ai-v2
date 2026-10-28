import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { searchRecords } from '../api'
import PageHeader from '../components/PageHeader'
import { CHARGE_STATUS, type ChargeStatus } from '../types'

export function DemoNotice({ text }: { text: string }) {
  return (
    <p className="shrink-0 rounded-2xl border border-accent-soft bg-accent-soft/30 px-4 py-2.5 text-[13px] text-accent">
      <span className="font-semibold">DEMO DATA · </span>
      {text}
    </p>
  )
}

export default function RecordsPage() {
  const [typed, setTyped] = useState('')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [area, setArea] = useState('')
  // every search is audited, so wait until the officer stops typing
  useEffect(() => {
    const t = setTimeout(() => setQ(typed.trim()), 400)
    return () => clearTimeout(t)
  }, [typed])
  const { data, error, isPending } = useQuery({
    queryKey: ['records', q, status, area],
    queryFn: () => searchRecords({ q, status, area }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader crumbs={[{ label: 'Records' }]} title="Criminal records" />
      {data && <DemoNotice text={data.notice} />}
      {data && (
        <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            ['People', data.summary.people],
            ['Cases', data.summary.cases],
            ['Convicted', data.summary.convicted],
            ['Pending', data.summary.pending],
            ['Acquitted', data.summary.acquitted],
          ].map(([label, n]) => (
            <div key={label} className="rounded-2xl bg-white px-4 py-3">
              <p className="text-xs text-muted">{label}</p>
              <p className="text-xl font-semibold text-ink">{n}</p>
            </div>
          ))}
        </div>
      )}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <label className="flex min-w-64 flex-1 items-center gap-2 rounded-full border border-line bg-white px-4 py-2">
          <Search size={15} className="text-muted" />
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Name, alias, record no., offence, BNS section, FIR no., area or mark (e.g. tattoo)"
            className="min-w-0 flex-1 bg-transparent text-[13px] outline-none"
          />
        </label>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-full border border-line bg-white px-3 py-2 text-[13px]">
          <option value="">Any status</option>
          {Object.entries(CHARGE_STATUS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select value={area} onChange={(e) => setArea(e.target.value)} className="rounded-full border border-line bg-white px-3 py-2 text-[13px]">
          <option value="">Any police station</option>
          {data?.areas.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error.message}</p>}
      {isPending && <p className="text-muted">Loading…</p>}
      {data && (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <p className="mb-2 text-xs text-muted">
            {data.total} {data.total === 1 ? 'person' : 'people'}
            {q || status || area ? ' match' : ''}
          </p>
          {data.total === 0 && <p className="rounded-2xl bg-white p-6 text-center text-[13px] text-muted">No records match. Run scripts.seed_records if the database is empty.</p>}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
            {data.items.map((r) => (
              <Link key={r.id} to={`/records/${r.id}`} className="flex gap-3 rounded-2xl bg-white p-3 hover:ring-2 hover:ring-ink/10">
                <img src={r.photo_url} alt="" className="h-24 w-20 shrink-0 rounded-lg bg-field object-cover" loading="lazy" />
                <div className="min-w-0 flex-1 text-[13px]">
                  <p className="truncate font-semibold text-ink">{r.name}</p>
                  <p className="truncate text-xs text-muted">
                    {r.alias ? `alias “${r.alias}” · ` : ''}
                    {r.record_no}
                  </p>
                  <p className="mt-1 truncate text-xs text-body">
                    {r.gender}, {r.age} · {r.area}
                  </p>
                  <p className="mt-1 truncate text-xs text-body">Latest: {r.latest_offence}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1 text-[11px]">
                    <span className="rounded bg-field px-1.5 py-0.5 text-ink">{r.cases} {r.cases === 1 ? 'case' : 'cases'}</span>
                    {r.convicted > 0 && <span className="rounded bg-accent-soft/50 px-1.5 py-0.5 text-accent">{r.convicted} convicted</span>}
                    {r.pending > 0 && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">{r.pending} pending</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

export const statusLabel = (s: ChargeStatus) => CHARGE_STATUS[s]

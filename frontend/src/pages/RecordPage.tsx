import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getRecord } from '../api'
import PageHeader from '../components/PageHeader'
import { CHARGE_STATUS, type ChargeStatus } from '../types'
import { DemoNotice } from './RecordsPage'

const BADGE: Record<ChargeStatus, string> = {
  under_investigation: 'bg-amber-100 text-amber-800',
  charge_sheeted: 'bg-orange-100 text-orange-800',
  convicted: 'bg-accent-soft/60 text-accent',
  acquitted: 'bg-field text-muted',
}

export default function RecordPage() {
  const id = Number(useParams().rid)
  const { data: r, error, isPending } = useQuery({ queryKey: ['record', id], queryFn: () => getRecord(id) })
  if (isPending) return <p className="p-4 text-muted">Loading…</p>
  if (error || !r) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{error?.message ?? 'Not found.'}</p>

  const facts = [
    ['Record no.', r.record_no],
    ['Alias', r.alias ?? '—'],
    ['Gender', r.gender],
    ['Age', String(r.age)],
    ['Height', `${r.height_cm} cm`],
    ['Build', r.build],
    ['Area', r.area],
    ['Identifying marks', r.marks ?? 'None recorded'],
  ]
  return (
    <>
      <PageHeader crumbs={[{ label: 'Records', to: '/records' }, { label: r.record_no, mono: true }]} title={r.name} />
      <Link to="/records" className="-mt-1 shrink-0 text-[13px] text-link hover:text-ink">
        ← All records
      </Link>
      <DemoNotice text={r.notice} />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto lg:grid-cols-[300px_minmax(0,1fr)]">
        <section className="flex flex-col gap-3 rounded-[22px] bg-white p-5">
          <img src={r.photo_url} alt={`Synthetic face for ${r.name}`} className="aspect-[4/5] w-full rounded-xl bg-field object-cover" />
          <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-2 gap-y-1.5 text-[13px]">
            {facts.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-[11px] text-faint">Face: {r.source} (synthetic, CC BY-NC 4.0)</p>
        </section>
        <section className="flex min-w-0 flex-col gap-3 rounded-[22px] bg-white p-5">
          <div className="grid grid-cols-4 gap-2">
            {[
              ['Cases', r.cases],
              ['Convicted', r.convicted],
              ['Pending', r.pending],
              ['Acquitted', r.acquitted],
            ].map(([k, n]) => (
              <div key={k} className="rounded-xl bg-field px-3 py-2">
                <p className="text-xs text-muted">{k}</p>
                <p className="text-lg font-semibold">{n}</p>
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">FIR no.</th>
                  <th className="py-2 pr-3 font-medium">Police station</th>
                  <th className="py-2 pr-3 font-medium">Section (BNS)</th>
                  <th className="py-2 pr-3 font-medium">Offence</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {r.charges.map((c) => (
                  <tr key={c.id} className="border-b border-line-soft">
                    <td className="py-2 pr-3 font-mono text-xs">{c.date}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{c.fir_no}</td>
                    <td className="py-2 pr-3">{c.police_station}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{c.section}</td>
                    <td className="py-2 pr-3">{c.offence}</td>
                    <td className="py-2">
                      <span className={`rounded px-2 py-0.5 text-xs ${BADGE[c.status]}`}>{CHARGE_STATUS[c.status]}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">A charge or arrest is not a conviction. Only cases marked Convicted ended in a finding of guilt.</p>
        </section>
      </div>
    </>
  )
}

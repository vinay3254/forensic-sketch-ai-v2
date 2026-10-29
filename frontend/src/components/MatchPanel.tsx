import { useMutation } from '@tanstack/react-query'
import { AlertTriangle, Search } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { findMatches } from '../api'
import type { Version } from '../types'

const BAND = {
  strong: { label: 'Strong lead', cls: 'bg-[#1baf7a]/15 text-[#13805a]' },
  possible: { label: 'Possible lead', cls: 'bg-amber-100 text-amber-800' },
  weak: { label: 'Weak', cls: 'bg-field text-muted' },
} as const

// compare this version's face with the records' mugshots; the closest are leads to check, never identifications
export default function MatchPanel({ caseId, version, onMakePhoto, busy }: { caseId: number; version: Version; onMakePhoto: () => void; busy: boolean }) {
  const search = useMutation({ mutationFn: () => findMatches(caseId, version.id) })
  useEffect(() => search.reset(), [version.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const d = search.data
  const best = d?.results[0]
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <p className="text-[13px] text-muted">
        Compare this face with the criminal records' mugshots. {version.photo_url ? 'The realistic photo is used.' : 'The sketch is used; a realistic photo matches far better.'}
      </p>
      {!version.photo_url && (
        <button onClick={onMakePhoto} disabled={busy} className="rounded-xl border border-line bg-white px-3 py-2 text-[13px] text-ink hover:border-ink disabled:opacity-50">
          Make realistic photo first (recommended)
        </button>
      )}
      <button
        onClick={() => search.mutate()}
        disabled={search.isPending || busy}
        className="flex items-center justify-center gap-2 rounded-xl bg-ink p-3 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50"
      >
        <Search size={15} /> {search.isPending ? 'Searching the records…' : d ? 'Search again' : 'Find possible matches'}
      </button>
      {search.error && <p className="rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{search.error.message}</p>}
      {d && (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          <p className="flex gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            {d.notice}
          </p>
          <p className="text-xs text-muted">
            Searched {d.searched} records using the {d.query}.{' '}
            {best && best.band === 'weak' && <b className="text-ink">No strong or possible match.</b>}
          </p>
          {d.results.map((r) => (
            <Link key={r.id} to={`/records/${r.id}`} className="flex items-center gap-3 rounded-2xl border border-line-soft p-2.5 hover:border-ink/30 hover:bg-field/60">
              <img src={r.photo_url} alt="" className="h-16 w-13 shrink-0 rounded-lg bg-field object-cover" />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-medium text-ink">{r.name}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${BAND[r.band].cls}`}>{BAND[r.band].label}</span>
                </span>
                <span className="block truncate text-xs text-muted">
                  {r.record_no} · {r.cases} {r.cases === 1 ? 'case' : 'cases'} · latest: {r.latest_offence}
                </span>
                <span className="mt-1 flex items-center gap-2">
                  <span className="h-1.5 flex-1 rounded-full bg-field">
                    <span className="block h-1.5 rounded-full bg-ink" style={{ width: `${Math.max(2, Math.min(100, r.score * 100))}%` }} />
                  </span>
                  <span className="w-10 text-right font-mono text-[11px] text-body">{Math.round(r.score * 100)}%</span>
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

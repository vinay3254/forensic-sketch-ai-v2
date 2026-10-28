import { useEffect, useRef, useState } from 'react'
import { ApiError, proportionPreview } from '../api'
import { PROPORTION_SLIDERS, type Proportions, type Version } from '../types'

interface Props {
  caseId: number
  version: Version
  busy: boolean
  onPreview: (url: string | null) => void
  onSave: (adj: Proportions) => void
}

// reshape the sketch (no AI): each change previews within a moment, Save makes a new version
export default function ProportionPanel({ caseId, version, busy, onPreview, onSave }: Props) {
  const [adj, setAdj] = useState<Proportions>({})
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)
  const url = useRef<string | null>(null)
  const changed = Object.values(adj).some((v) => v)

  // a new version starts from zero
  useEffect(() => setAdj({}), [version.id])

  useEffect(() => {
    const show = (next: string | null) => {
      if (url.current) URL.revokeObjectURL(url.current)
      url.current = next
      onPreview(next)
    }
    if (!changed) {
      show(null)
      setError(undefined)
      return
    }
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setLoading(true)
      proportionPreview(caseId, version.id, adj, ctrl.signal)
        .then((u) => {
          show(u)
          setError(undefined)
        })
        .catch((e) => {
          if (e instanceof ApiError) setError(e.message)
        })
        .finally(() => setLoading(false))
    }, 60)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [adj, caseId, version.id, changed, onPreview])

  // leaving the panel shows the stored sketch again
  useEffect(
    () => () => {
      if (url.current) URL.revokeObjectURL(url.current)
      onPreview(null)
    },
    [onPreview],
  )

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <p className="text-[13px] text-muted">
        Drag until the face looks right to the witness. Only this sketch is reshaped, nothing is redrawn.
      </p>
      <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto pr-1">
        {PROPORTION_SLIDERS.map(([key, label, less, more]) => {
          const v = adj[key] ?? 0
          return (
            <label key={key} className="flex flex-col gap-1 text-[13px]">
              <span className="flex justify-between">
                <span className="text-ink">{label}</span>
                <span className={`font-mono text-xs ${v ? 'text-accent' : 'text-faint'}`}>
                  {v > 0 ? '+' : ''}
                  {Math.round(v * 100)}%
                </span>
              </span>
              <input
                type="range"
                min={-1}
                max={1}
                step={0.05}
                value={v}
                disabled={busy}
                onChange={(e) => setAdj((a) => ({ ...a, [key]: Number(e.target.value) }))}
                onDoubleClick={() => setAdj((a) => ({ ...a, [key]: 0 }))}
                className="accent-accent"
              />
              <span className="flex justify-between text-[11px] text-faint">
                <span>{less}</span>
                <span>{more}</span>
              </span>
            </label>
          )
        })}
      </div>
      {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>}
      <div className="flex shrink-0 gap-2">
        <button
          onClick={() => setAdj({})}
          disabled={!changed || busy}
          className="rounded-xl border border-[#dcdcd7] bg-white px-4 py-3 text-[13px] font-medium text-ink hover:border-ink disabled:opacity-50"
        >
          Reset
        </button>
        <button
          onClick={() => onSave(adj)}
          disabled={!changed || busy || !!error}
          className="flex-1 rounded-xl bg-ink p-3 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50"
        >
          {loading ? 'Updating preview…' : 'Save as new version'}
        </button>
      </div>
    </div>
  )
}

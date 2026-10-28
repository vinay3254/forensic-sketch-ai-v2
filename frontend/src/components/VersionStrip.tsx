import type { Version } from '../types'

interface Props {
  versions: Version[]
  selectedId: number | undefined
  busy: boolean
  onSelect: (id: number) => void
  onRevert: (id: number) => void
}

export default function VersionStrip({ versions, selectedId, busy, onSelect, onRevert }: Props) {
  const latest = versions.at(-1)
  return (
    <div className="flex items-end gap-3 overflow-x-auto pb-2">
      {versions.map((v) => (
        <div key={v.id} className="flex shrink-0 flex-col items-center gap-1">
          <button
            onClick={() => onSelect(v.id)}
            title={v.instruction}
            className={`h-24 w-16 overflow-hidden rounded border-2 ${v.id === selectedId ? 'border-blue-600' : 'border-transparent'}`}
          >
            <img src={v.image_url} alt={`v${v.version_no}`} className="h-full w-full object-cover" />
          </button>
          <span className="text-xs text-slate-600">
            v{v.version_no}
            {v.kind !== 'generate' && v.kind !== 'refine' ? ` · ${v.kind}` : ''}
          </span>
          {v.id === selectedId && v.id !== latest?.id && (
            <button onClick={() => onRevert(v.id)} disabled={busy} className="text-xs text-blue-700 hover:underline disabled:opacity-50">
              Revert to this
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

import { Camera, History, Undo2 } from 'lucide-react'
import type { Version } from '../types'
import { Badge, Button, CardHeader, type Tone } from './ui'

const KIND: Record<string, { label: string; tone: Tone }> = {
  generate: { label: 'Generated', tone: 'ink' },
  refine: { label: 'Refined', tone: 'blue' },
  revert: { label: 'Reverted', tone: 'amber' },
}

interface Props {
  versions: Version[]
  selectedId: number | undefined
  busy: boolean
  onSelect: (id: number) => void
  onRevert: (id: number) => void
}

export default function VersionStrip({ versions, selectedId, busy, onSelect, onRevert }: Props) {
  const latest = versions.at(-1)
  const selected = versions.find((v) => v.id === selectedId)
  return (
    <div>
      <CardHeader
        title="Version history"
        icon={<History className="size-4" />}
        action={
          selected &&
          selected.id !== latest?.id && (
            <Button size="sm" variant="secondary" onClick={() => onRevert(selected.id)} disabled={busy} icon={<Undo2 className="size-3.5" />}>
              Revert to v{selected.version_no}
            </Button>
          )
        }
      />
      <div className="flex gap-4 overflow-x-auto px-5 py-4">
        {versions.map((v) => {
          const kind = KIND[v.kind] ?? { label: v.kind, tone: 'neutral' as Tone }
          const active = v.id === selectedId
          return (
            <button key={v.id} onClick={() => onSelect(v.id)} className="group w-28 shrink-0 text-left" title={v.instruction}>
              <div
                className={`paper-grain relative aspect-[2/3] overflow-hidden rounded-md ring-1 transition ${
                  active ? 'ring-2 ring-brass-500 shadow-lift' : 'ring-paper-300 group-hover:ring-ink-300'
                }`}
              >
                <img src={v.image_url} alt={`v${v.version_no}`} loading="lazy" className="h-full w-full object-cover" />
                {v.photo_url && (
                  <span className="absolute right-1.5 top-1.5 rounded bg-white/90 p-0.5 text-ink-700 shadow-sm" title="Realistic photo available">
                    <Camera className="size-3" />
                  </span>
                )}
              </div>
              <div className="mt-2 flex items-center gap-1.5">
                <span className="font-mono text-xs font-medium text-ink-900">v{v.version_no}</span>
                <Badge tone={kind.tone}>{kind.label}</Badge>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-ink-500">{v.instruction}</p>
            </button>
          )
        })}
      </div>
    </div>
  )
}

import type { Version } from '../types'

export type View = 'sketch' | 'photo'

interface Props {
  versions: Version[]
  version: Version | undefined
  view: View
  busy: boolean
  onView: (view: View) => void
  onSelect: (id: number) => void
  onRevert: (id: number) => void
  onNew: () => void
}

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

// the sketch on warm paper, with the version strip under it
export default function FaceCanvas({ versions, version, view, busy, onView, onSelect, onRevert, onNew }: Props) {
  const showPhoto = view === 'photo' && !!version?.photo_url
  const src = showPhoto ? version!.photo_url! : version?.image_url
  const latest = versions.at(-1)
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col gap-3">
      <div className="flex items-center justify-between px-1 pt-1">
        <div className="flex items-center gap-2">
          {version && <span className="rounded-md bg-ink px-[7px] py-[3px] font-mono text-[11px] text-white">v{version.version_no}</span>}
          {version?.photo_url ? (
            <div className="flex rounded-full bg-white/70 p-0.5 text-xs">
              {(['sketch', 'photo'] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => onView(v)}
                  className={`rounded-full px-2.5 py-1 ${(v === 'photo') === showPhoto ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}
                >
                  {v === 'sketch' ? 'Pencil' : 'Realistic photo'}
                </button>
              ))}
            </div>
          ) : (
            <span className="text-[13px] text-muted">{version ? 'Pencil · front view' : 'No sketch yet'}</span>
          )}
        </div>
        {version && <span className="text-xs text-muted">{version.kind === 'generate' ? 'Generated' : 'Updated'} {time(version.created_at)}</span>}
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center [container-type:size]">
        {version ? (
          <img
            src={src}
            alt={`Version ${version.version_no}`}
            className="aspect-[2/3] w-[min(100cqw,66.6cqh)] rounded-[14px] object-cover shadow-[0_1px_0_rgba(0,0,0,0.04),0_18px_40px_-20px_rgba(40,30,10,0.35)]"
          />
        ) : (
          <p className="max-w-60 text-center text-[13px] text-muted">Enter the witness description, or start a witness interview, to draw the first sketch.</p>
        )}
        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-[14px] bg-cream/80">
            <div className="size-10 animate-spin rounded-full border-4 border-line border-t-ink" />
            <p className="text-[13px] text-body">Working… this can take up to a minute</p>
          </div>
        )}
      </div>
      {versions.length > 0 && (
        <div className="flex items-center gap-2.5 rounded-[14px] bg-white/70 p-2">
          <div className="flex min-w-0 gap-2.5 overflow-x-auto">
            {versions.map((v) => (
              <button
                key={v.id}
                onClick={() => onSelect(v.id)}
                title={`v${v.version_no}: ${v.instruction}`}
                className={`h-[62px] w-11 shrink-0 overflow-hidden rounded-lg ${v.id === version?.id ? 'outline-2 outline-offset-1 outline-violet' : ''}`}
              >
                <img src={v.image_url} alt={`v${v.version_no}`} className="size-full object-cover" />
              </button>
            ))}
          </div>
          <button
            onClick={onNew}
            disabled={busy}
            title="New sketch from a new description"
            className="grid h-[62px] w-11 shrink-0 place-items-center rounded-lg border-[1.5px] border-dashed border-[#c9c6bb] text-lg text-[#9a978c] hover:border-ink hover:text-ink"
          >
            +
          </button>
          <div className="ml-auto flex flex-col items-end gap-1 pr-1.5 text-xs text-muted">
            {versions.length} version{versions.length === 1 ? '' : 's'}
            {version && version.id !== latest?.id && (
              <button onClick={() => onRevert(version.id)} disabled={busy} className="text-link hover:text-ink disabled:opacity-50">
                Revert to v{version.version_no}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

import type { Version } from '../types'

export type View = 'sketch' | 'photo'

interface Props {
  version: Version | undefined
  view: View
  busy: boolean
  onView: (view: View) => void
}

export default function FaceCanvas({ version, view, busy, onView }: Props) {
  const showPhoto = view === 'photo' && !!version?.photo_url
  const src = showPhoto ? version!.photo_url! : version?.image_url
  return (
    <div className="flex w-full max-w-sm flex-col items-center gap-2">
      {version?.photo_url && (
        <div className="flex rounded border bg-white text-sm">
          {(['sketch', 'photo'] as const).map((v) => (
            <button
              key={v}
              onClick={() => onView(v)}
              className={`px-4 py-1 ${(v === 'photo') === showPhoto ? 'bg-slate-900 text-white' : 'hover:bg-slate-100'}`}
            >
              {v === 'sketch' ? 'Sketch' : 'Realistic photo'}
            </button>
          ))}
        </div>
      )}
      <div className="relative flex aspect-[2/3] w-full items-center justify-center overflow-hidden rounded-lg bg-white shadow">
        {version ? (
          <img src={src} alt={`Version ${version.version_no}`} className="h-full w-full object-cover" />
        ) : (
          <p className="px-6 text-center text-slate-500">No sketch yet. Enter the witness description to generate one.</p>
        )}
        {version && <span className="absolute left-2 top-2 rounded bg-black/60 px-2 py-0.5 text-xs text-white">v{version.version_no}</span>}
        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/80">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 border-t-slate-900" />
            <p className="text-sm text-slate-700">Working… this can take up to a minute</p>
          </div>
        )}
      </div>
    </div>
  )
}

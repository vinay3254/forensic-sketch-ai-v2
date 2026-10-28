import { Camera, PenLine } from 'lucide-react'
import type { Version } from '../types'

export type View = 'sketch' | 'photo'

interface Props {
  version: Version | undefined
  view: View
  busy: boolean
  busyLabel: string
  onView: (view: View) => void
}

export default function FaceCanvas({ version, view, busy, busyLabel, onView }: Props) {
  const showPhoto = view === 'photo' && !!version?.photo_url
  const src = showPhoto ? version!.photo_url! : version?.image_url
  return (
    <div className="flex w-full flex-col items-center gap-4">
      <div className="flex h-9 items-center">
        {version?.photo_url ? (
          <div className="flex rounded-xl bg-white p-1 shadow-card ring-1 ring-paper-200">
            {(['sketch', 'photo'] as const).map((v) => {
              const active = (v === 'photo') === showPhoto
              return (
                <button
                  key={v}
                  onClick={() => onView(v)}
                  className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1 text-xs font-medium transition ${
                    active ? 'bg-ink-900 text-white shadow-sm' : 'text-ink-500 hover:text-ink-900'
                  }`}
                >
                  {v === 'sketch' ? <PenLine className="size-3.5" /> : <Camera className="size-3.5" />}
                  {v === 'sketch' ? 'Sketch' : 'Realistic photo'}
                </button>
              )
            })}
          </div>
        ) : (
          version && <span className="text-xs text-ink-400">Pencil sketch · v{version.version_no}</span>
        )}
      </div>

      <div className="paper-grain relative aspect-[2/3] w-full max-w-md overflow-hidden rounded-sm shadow-lift ring-1 ring-paper-300">
        {version ? (
          <img key={src} src={src} alt={`Version ${version.version_no}`} className="h-full w-full object-cover animate-in" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-10 text-center">
            <PenLine className="size-8 text-ink-300" strokeWidth={1.25} />
            <p className="text-sm text-ink-500">The sketch will appear here once you submit the witness description.</p>
          </div>
        )}
        {version && (
          <span className="absolute left-3 top-3 rounded-md bg-ink-950/80 px-2 py-0.5 font-mono text-[11px] text-white backdrop-blur">
            v{version.version_no}
          </span>
        )}
        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-paper-50/85 backdrop-blur-[2px]">
            <div className="relative h-1 w-40 overflow-hidden rounded-full bg-paper-300">
              <div className="absolute inset-y-0 w-1/2 rounded-full bg-brass-500" style={{ animation: 'shimmer 1.2s ease-in-out infinite' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-ink-900">{busyLabel}</p>
              <p className="mt-0.5 text-xs text-ink-500">This can take up to a minute</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

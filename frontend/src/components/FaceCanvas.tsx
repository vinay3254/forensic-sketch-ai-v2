import type { Version } from '../types'

export default function FaceCanvas({ version, busy }: { version: Version | undefined; busy: boolean }) {
  return (
    <div className="relative flex aspect-[2/3] w-full max-w-sm items-center justify-center overflow-hidden rounded-lg bg-slate-200">
      {version ? (
        <img src={version.image_url} alt={`Version ${version.version_no}`} className="h-full w-full object-cover" />
      ) : (
        <p className="px-6 text-center text-slate-500">No face yet. Enter the witness description to generate one.</p>
      )}
      {version && <span className="absolute left-2 top-2 rounded bg-black/60 px-2 py-0.5 text-xs text-white">v{version.version_no}</span>}
      {busy && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/80">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 border-t-slate-900" />
          <p className="text-sm text-slate-700">Generating… this can take up to a minute</p>
        </div>
      )}
    </div>
  )
}

import { exportUrl, sheetUrl } from '../api'
import { ATTRIBUTE_KEYS, type Version } from '../types'

const label = (key: string) => key.replace('_', ' ').replace(/^\w/, (c) => c.toUpperCase())

interface Props {
  caseId: number
  version: Version | undefined
  busy: boolean
  onMakePhoto: () => void
}

export default function AttributePanel({ caseId, version, busy, onMakePhoto }: Props) {
  const filled = version ? ATTRIBUTE_KEYS.filter((k) => version.attributes[k]).length : 0
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-semibold">Attributes</span>
        <span className="text-xs text-muted">
          {filled} of {ATTRIBUTE_KEYS.length} described
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[#f0f0ec]">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round((filled / ATTRIBUTE_KEYS.length) * 100)}%` }} />
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {ATTRIBUTE_KEYS.map((k) => {
          const v = version?.attributes[k]
          return (
            <div key={k} className="grid grid-cols-[96px_minmax(0,1fr)] gap-2.5 border-b border-line-soft py-1.5 text-[13px]">
              <span className="text-muted">{label(k)}</span>
              <span className={v ? 'text-ink' : 'text-ghost'}>
                {v ?? '—'}
                {version?.uncertain.includes(k) && (
                  <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[11px] text-amber-800" title="The witness was unsure about this">
                    uncertain
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>
      {version && (
        <div className="flex shrink-0 flex-col gap-2">
          <a
            href={exportUrl(caseId, version.id, 'sketch')}
            download
            className="rounded-xl bg-ink p-3 text-center text-[13px] font-medium text-white hover:bg-ink-2"
          >
            Export sketch
          </a>
          {version.photo_url ? (
            <a
              href={exportUrl(caseId, version.id, 'photo')}
              download
              className="rounded-xl border border-[#dcdcd7] bg-white p-3 text-center text-[13px] font-medium text-ink hover:border-ink"
            >
              Export realistic photo
            </a>
          ) : (
            <button
              onClick={onMakePhoto}
              disabled={busy}
              className="rounded-xl border border-[#dcdcd7] bg-white p-3 text-[13px] font-medium text-ink hover:border-ink disabled:opacity-50"
            >
              Make realistic photo
            </button>
          )}
          <div className="flex justify-center gap-3 pt-1 text-[13px] text-muted">
            Case sheet
            <a href={sheetUrl(caseId, version.id, 'pdf')} download className="text-link hover:text-ink">
              PDF
            </a>
            <a href={sheetUrl(caseId, version.id, 'png')} download className="text-link hover:text-ink">
              PNG
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

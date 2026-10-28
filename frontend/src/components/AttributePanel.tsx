import { exportUrl } from '../api'
import { ATTRIBUTE_KEYS, type Version } from '../types'

const label = (key: string) => key.replace('_', ' ').replace(/^\w/, (c) => c.toUpperCase())

export default function AttributePanel({ caseId, version }: { caseId: number; version: Version | undefined }) {
  return (
    <div className="space-y-4">
      <h2 className="font-semibold">Attributes</h2>
      {version ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {ATTRIBUTE_KEYS.map((k) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{label(k)}</dt>
              <dd>{version.attributes[k] ?? '—'}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-slate-500">—</p>
      )}
      {version && (
        <div className="flex gap-2">
          <a href={exportUrl(caseId, version.id, 'photo')} download className="rounded bg-slate-900 px-3 py-2 text-sm text-white">
            Export photo
          </a>
          <a href={exportUrl(caseId, version.id, 'sketch')} download className="rounded border border-slate-900 px-3 py-2 text-sm">
            Export sketch
          </a>
        </div>
      )}
    </div>
  )
}

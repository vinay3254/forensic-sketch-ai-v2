import { Camera, Download, ScanFace } from 'lucide-react'
import { exportUrl } from '../api'
import { ATTRIBUTE_KEYS, type Version } from '../types'
import { Button, buttonClass, CardHeader } from './ui'

const label = (key: string) => key.replace('_', ' ').replace(/^\w/, (c) => c.toUpperCase())

interface Props {
  caseId: number
  version: Version | undefined
  busy: boolean
  onMakePhoto: () => void
}

export default function AttributePanel({ caseId, version, busy, onMakePhoto }: Props) {
  const filled = version ? ATTRIBUTE_KEYS.filter((k) => version.attributes[k]) : []
  const empty = version ? ATTRIBUTE_KEYS.filter((k) => !version.attributes[k]) : []
  return (
    <div className="flex h-full flex-col">
      <CardHeader
        title="Attributes"
        icon={<ScanFace className="size-4" />}
        action={version && <span className="text-[11px] text-ink-400">{filled.length} of {ATTRIBUTE_KEYS.length} described</span>}
      />
      <div className="flex-1 px-5 py-4">
        {version ? (
          <>
            <dl className="space-y-2.5">
              {filled.map((k) => (
                <div key={k}>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-ink-400">{label(k)}</dt>
                  <dd className="text-sm text-ink-900">{version.attributes[k]}</dd>
                </div>
              ))}
            </dl>
            {empty.length > 0 && (
              <p className="mt-4 border-t border-dashed border-paper-300 pt-3 text-[11px] leading-relaxed text-ink-400">
                Not described: {empty.map(label).join(', ')}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-ink-500">Attributes the AI extracts from the description will be listed here.</p>
        )}
      </div>
      {version && (
        <div className="space-y-2 border-t border-paper-200 p-4">
          <a href={exportUrl(caseId, version.id, 'sketch')} download className={`${buttonClass('primary')} w-full`}>
            <Download className="size-4" />
            Export sketch
          </a>
          {version.photo_url ? (
            <a href={exportUrl(caseId, version.id, 'photo')} download className={`${buttonClass('secondary')} w-full`}>
              <Download className="size-4" />
              Export realistic photo
            </a>
          ) : (
            <Button variant="secondary" className="w-full" onClick={onMakePhoto} disabled={busy} icon={<Camera className="size-4" />}>
              Make realistic photo
            </Button>
          )}
          <p className="pt-1 text-center text-[10px] text-ink-400">Exports carry the case number, version and your name.</p>
        </div>
      )}
    </div>
  )
}

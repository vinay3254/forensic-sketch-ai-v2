import { langName } from '../types'

interface Props {
  lang: string
  english: string | null | undefined
  busy: boolean
  error: string | null
  disabled: boolean
  onTranslate: () => void
}

// the English the sketch will be made from, shown under words spoken in another language
export default function TranslationPanel({ lang, english, busy, error, disabled, onTranslate }: Props) {
  return (
    <div className="rounded-2xl border border-line bg-field p-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-ink">English translation</span>
        <span className="text-xs text-muted">from {langName(lang)} · used for the sketch</span>
        {!disabled && (
          <button
            type="button"
            onClick={onTranslate}
            disabled={busy}
            className="ml-auto rounded-full border border-line bg-white px-3 py-1 text-xs hover:border-ink disabled:opacity-50"
          >
            {busy ? 'Translating…' : english ? 'Translate again' : 'Translate'}
          </button>
        )}
      </div>
      <p className={`mt-1.5 whitespace-pre-wrap ${english ? 'text-ink' : 'text-ghost'}`}>
        {english ? `“${english}”` : busy ? 'Translating…' : 'Not translated yet. Read it back to the witness once translated.'}
      </p>
      {error && <p className="mt-1 text-red-600">{error}</p>}
    </div>
  )
}

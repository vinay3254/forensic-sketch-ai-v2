import type { InputSource } from '../types'
import { speechSupported, useSpeech } from './useSpeech'

export const MAX_TEXT = 2000

const SPEECH_LANGS = [
  { code: 'en-IN', label: 'English (India)' },
  { code: 'en-US', label: 'English (US)' },
  { code: 'hi-IN', label: 'Hindi' },
  { code: 'kn-IN', label: 'Kannada' },
]

interface Props {
  value: string
  source: InputSource | null
  rows: number
  disabled: boolean
  lang: string
  onLang: (lang: string) => void
  onType: (text: string) => void
  onDictate: (phrase: string) => void
}

export default function AnswerBox({ value, source, rows, disabled, lang, onLang, onType, onDictate }: Props) {
  const speech = useSpeech(lang, onDictate)

  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span className="text-sm font-medium">Witness's words, exactly as said</span>
        {speechSupported ? (
          <div className="ml-auto flex items-center gap-2">
            <select
              value={lang}
              onChange={(e) => onLang(e.target.value)}
              disabled={speech.listening}
              className="rounded border px-2 py-1 text-xs disabled:opacity-50"
              aria-label="Speech language"
            >
              {SPEECH_LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={disabled}
              onClick={speech.listening ? speech.stop : speech.start}
              className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-medium disabled:opacity-50 ${
                speech.listening ? 'bg-red-600 text-white' : 'border border-slate-900'
              }`}
            >
              <span className={`size-2 rounded-full ${speech.listening ? 'animate-pulse bg-white' : 'bg-red-600'}`} />
              {speech.listening ? 'Stop dictation' : 'Dictate'}
            </button>
          </div>
        ) : (
          <span className="ml-auto text-xs text-slate-500">Dictation needs Chrome or Edge. Type the answer instead.</span>
        )}
      </div>
      <textarea
        value={value}
        maxLength={MAX_TEXT}
        disabled={disabled}
        onChange={(e) => onType(e.target.value)}
        rows={rows}
        placeholder="Type or dictate what the witness says. Do not correct or summarise."
        className={`w-full resize-y rounded border p-3 text-sm disabled:bg-slate-50 ${speech.listening ? 'border-red-400 ring-2 ring-red-100' : ''}`}
      />
      {speech.listening && (
        <p className="mt-1 min-h-5 text-sm italic text-slate-500">{speech.interim || 'Listening…'}</p>
      )}
      {speech.error && <p className="mt-1 text-sm text-red-600">{speech.error}</p>}
      <span className="text-xs text-slate-500">
        {value.length}/{MAX_TEXT}
        {source && ` · ${source === 'speech' ? 'dictated' : source === 'mixed' ? 'typed and dictated' : 'typed'}`}
      </span>
    </div>
  )
}

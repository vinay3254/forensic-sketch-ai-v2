import { isEnglish, type InputSource } from '../types'
import TranslationPanel from './TranslationPanel'
import VoiceInput from './VoiceInput'

export const MAX_TEXT = 2000

interface Props {
  value: string
  source: InputSource | null
  rows: number
  disabled: boolean
  lang: string // the language picker
  wordsLang: string | null // the language these words were given in
  english: string | null | undefined
  translating: boolean
  translateError: string | null
  onLang: (lang: string) => void
  onType: (text: string) => void
  onDictate: (phrase: string) => void
  onTranslate: () => void
}

export default function AnswerBox(p: Props) {
  const other = !isEnglish(p.wordsLang) && p.value.trim() !== ''
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="pt-1 text-sm font-medium">Witness's words, exactly as said</span>
        {!p.disabled && (
          <VoiceInput
            lang={p.lang}
            disabled={p.disabled}
            onLang={p.onLang}
            onDictate={p.onDictate}
            // translate as soon as the witness stops, so the officer can read it back
            onStopped={() => !isEnglish(p.lang) && p.onTranslate()}
          />
        )}
      </div>
      <textarea
        value={p.value}
        maxLength={MAX_TEXT}
        disabled={p.disabled}
        onChange={(e) => p.onType(e.target.value)}
        rows={p.rows}
        placeholder="Type, or press Record and let the witness speak. Do not correct or summarise."
        className="w-full resize-y rounded border p-3 text-sm disabled:bg-slate-50"
      />
      <span className="text-xs text-slate-500">
        {p.value.length}/{MAX_TEXT}
        {p.source && ` · ${p.source === 'speech' ? 'dictated' : p.source === 'mixed' ? 'typed and dictated' : 'typed'}`}
      </span>
      {other && (
        <TranslationPanel
          lang={p.wordsLang!}
          english={p.english}
          busy={p.translating}
          error={p.translateError}
          disabled={p.disabled}
          onTranslate={p.onTranslate}
        />
      )}
    </div>
  )
}

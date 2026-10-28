import { useRef, useState, type FormEvent } from 'react'
import { isEnglish } from '../types'
import VoiceInput from './VoiceInput'

export const MAX_TEXT = 2000

interface Props {
  initialText?: string
  busy: boolean
  replacing: boolean
  onSubmit: (description: string, lang?: string) => void // lang: the description is translated first
  onCancel?: () => void
}

export default function DescriptionForm({
  busy,
  replacing,
  onSubmit,
  onCancel,
  initialText = '',
}: Props) {
  const [text, setText] = useState(initialText)
  const [lang, setLang] = useState('en-IN')
  const said = useRef<string | null>(null) // language of dictated words; typed words follow the picker

  function submit(e: FormEvent) {
    e.preventDefault()
    const from = said.current ?? lang
    onSubmit(text.trim(), isEnglish(from) ? undefined : from)
  }

  return (
    <form onSubmit={submit} className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="size-2 rounded-full bg-accent" />
        <span className="text-[15px] font-semibold">Witness description</span>
      </div>
      <VoiceInput
        lang={lang}
        disabled={busy}
        onLang={(l) => {
          setLang(l)
          said.current = null
        }}
        onDictate={(phrase) => {
          said.current = lang
          setText((t) => (t && !/\s$/.test(t) ? `${t} ${phrase}` : t + phrase).slice(0, MAX_TEXT))
        }}
      />
      <textarea
        value={text}
        maxLength={MAX_TEXT}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe the face, or press Record and speak in any listed language: age, skin tone, face shape, eyes, nose, hair, marks…"
        className="min-h-40 flex-1 resize-none rounded-2xl border border-line bg-field p-3.5 text-[13px] leading-[1.55] disabled:opacity-60"
      />
      <div className="flex items-center gap-2 text-[13px]">
        <span className="font-mono text-[11px] text-faint">
          {text.length} / {MAX_TEXT}
        </span>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="ml-auto rounded-full px-3 py-2 text-muted hover:text-ink"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className={`${onCancel ? '' : 'ml-auto '}rounded-full bg-ink px-[18px] py-2.5 font-medium text-white hover:bg-ink-2 disabled:opacity-50`}
        >
          {replacing ? 'Generate new sketch' : 'Generate'}
          {!isEnglish(said.current ?? lang) && ' (translates first)'}
        </button>
      </div>
    </form>
  )
}

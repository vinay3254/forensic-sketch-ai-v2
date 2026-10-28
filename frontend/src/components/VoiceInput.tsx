import { Mic, Square } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { SPEECH_LANGS } from '../types'
import { speechSupported, useSpeech } from './useSpeech'

interface Props {
  lang: string
  disabled: boolean
  onLang: (lang: string) => void
  onDictate: (phrase: string) => void
  onStopped?: () => void // recording ended (button or silence)
}

// language picker + record/stop; recognised phrases are handed over exactly as heard
export default function VoiceInput({ lang, disabled, onLang, onDictate, onStopped }: Props) {
  const speech = useSpeech(lang, onDictate)
  const was = useRef(false)
  const stopped = useRef(onStopped)
  useEffect(() => {
    stopped.current = onStopped
  }, [onStopped])
  useEffect(() => {
    if (was.current && !speech.listening) stopped.current?.()
    was.current = speech.listening
  }, [speech.listening])

  if (!speechSupported) {
    return <p className="text-xs text-muted">Voice input needs Chrome or Edge. Type instead.</p>
  }
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={lang}
          onChange={(e) => onLang(e.target.value)}
          disabled={speech.listening}
          aria-label="Language the witness is speaking"
          className="min-w-0 rounded-full border border-line bg-white px-3 py-1.5 text-xs disabled:opacity-50"
        >
          {SPEECH_LANGS.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
        {speech.listening ? (
          <button
            type="button"
            onClick={speech.stop}
            className="flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-1.5 text-xs font-medium text-white"
          >
            <Square className="size-3 fill-current" /> Stop
            <span className="size-2 animate-pulse rounded-full bg-white" />
          </button>
        ) : (
          <button
            type="button"
            onClick={speech.start}
            disabled={disabled}
            title="Record the witness speaking"
            className="flex items-center gap-1.5 rounded-full border border-ink px-3.5 py-1.5 text-xs font-medium text-ink hover:bg-ink hover:text-white disabled:opacity-50"
          >
            <Mic className="size-3.5" /> Record
          </button>
        )}
      </div>
      {speech.listening && <p className="min-h-5 text-[13px] italic text-muted">{speech.interim || 'Listening…'}</p>}
      {speech.error && <p className="text-[13px] text-red-600">{speech.error}</p>}
    </div>
  )
}

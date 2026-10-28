import { ArrowUp, Mic, Square } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { speechSupported, useSpeech } from './useSpeech'

export const MAX_TEXT = 2000

export interface Chip {
  label: string
  icon?: ReactNode
  onClick: () => void
}

interface Props {
  placeholder: string
  busy?: boolean
  chips?: Chip[]
  onSubmit: (text: string) => void
  value?: string
  onChange?: (text: string) => void
  rows?: number
  autoFocus?: boolean
}

const chipClass =
  'flex items-center gap-1.5 rounded-full border border-black/5 bg-white/80 px-3.5 py-2 text-[13px] text-body shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:text-ink disabled:opacity-50'

// the rounded prompt bar: text, a row of chips, dictation and a round send button
export default function Composer({ placeholder, busy, chips = [], onSubmit, value, onChange, rows = 2, autoFocus }: Props) {
  const [own, setOwn] = useState('')
  const text = value ?? own
  const setText = onChange ?? setOwn
  const speech = useSpeech('en-IN', (phrase) => setText((text && !/\s$/.test(text) ? `${text} ${phrase}` : text + phrase).slice(0, MAX_TEXT)))

  function send() {
    if (busy || !text.trim()) return
    onSubmit(text.trim())
    setText('')
  }

  return (
    <div className="rounded-[22px] border border-white bg-white/70 p-3 shadow-[0_10px_30px_-18px_rgba(60,40,30,0.35)] backdrop-blur-xl">
      <div className="flex items-start gap-2 px-1.5">
        <span className="pt-2 text-violet">✦</span>
        <textarea
          value={text}
          rows={rows}
          autoFocus={autoFocus}
          maxLength={MAX_TEXT}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          placeholder={placeholder}
          className="min-w-0 flex-1 resize-none border-0 bg-transparent py-1.5 text-[14px] leading-[1.55] placeholder:text-faint disabled:opacity-60"
        />
      </div>
      {speech.listening && <p className="px-8 text-[13px] italic text-muted">{speech.interim || 'Listening…'}</p>}
      <div className="mt-2 flex items-center gap-2">
        <div className="flex min-w-0 flex-wrap gap-2">
          {chips.map((c) => (
            <button key={c.label} type="button" onClick={c.onClick} disabled={busy} className={chipClass}>
              {c.icon}
              {c.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {speechSupported && (
            <button
              type="button"
              onClick={speech.listening ? speech.stop : speech.start}
              disabled={busy}
              title={speech.listening ? 'Stop dictation' : 'Dictate'}
              className={`grid size-9 place-items-center rounded-full border border-black/5 ${speech.listening ? 'bg-red-500 text-white' : 'bg-white/80 text-body hover:text-ink'}`}
            >
              {speech.listening ? <Square size={14} /> : <Mic size={16} />}
            </button>
          )}
          <button
            type="button"
            onClick={send}
            disabled={busy || !text.trim()}
            title="Send"
            className="grid size-9 place-items-center rounded-full bg-ink text-white shadow-[0_4px_12px_rgba(0,0,0,0.25)] hover:bg-ink-2 disabled:opacity-40"
          >
            {busy ? <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <ArrowUp size={16} />}
          </button>
        </div>
      </div>
      {speech.error && <p className="mt-1 px-2 text-[13px] text-red-600">{speech.error}</p>}
    </div>
  )
}

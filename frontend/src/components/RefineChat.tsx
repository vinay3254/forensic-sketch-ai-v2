import { ArrowUp, MessagesSquare, PenLine, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatMsg } from '../types'
import { MAX_TEXT } from './DescriptionForm'
import { Button, CardHeader } from './ui'

const SUGGESTIONS = ['Make the jaw wider', 'Add a thin moustache', 'Thicker eyebrows', 'Make him look older', 'Add glasses', 'Shorter hair']

interface Props {
  chat: ChatMsg[]
  busy: boolean
  onSend: (message: string) => void
  onStartOver: () => void
}

function Bubble({ m }: { m: ChatMsg }) {
  const mine = m.role === 'user'
  const time = new Date(m.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return (
    <div className={`flex gap-2.5 ${mine ? 'flex-row-reverse' : ''}`}>
      <div
        className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
          mine ? 'bg-ink-900 text-white' : 'bg-brass-500/15 text-brass-600'
        }`}
      >
        {mine ? 'YOU' : <PenLine className="size-3.5" />}
      </div>
      <div className={`max-w-[80%] ${mine ? 'items-end' : ''} flex flex-col`}>
        <p
          className={`whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
            mine ? 'rounded-tr-md bg-ink-900 text-white' : 'rounded-tl-md bg-paper-100 text-ink-900 ring-1 ring-paper-200'
          }`}
        >
          {m.content}
        </p>
        <span className="mt-1 px-1 text-[10px] text-ink-400">
          {time}
          {m.version_id !== null && !mine && ' · new version'}
        </span>
      </div>
    </div>
  )
}

export default function RefineChat({ chat, busy, onSend, onStartOver }: Props) {
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [chat.length, busy])

  function send(message: string) {
    onSend(message)
    setText('')
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    send(text.trim())
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <CardHeader
        title="Refine with the witness"
        icon={<MessagesSquare className="size-4" />}
        action={
          <Button size="sm" variant="ghost" onClick={onStartOver} disabled={busy} icon={<RotateCcw className="size-3.5" />}>
            Start over
          </Button>
        }
      />
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {chat.map((m) => (
          <Bubble key={m.id} m={m} />
        ))}
        {busy && (
          <div className="flex gap-2.5">
            <div className="flex size-7 items-center justify-center rounded-full bg-brass-500/15 text-brass-600">
              <PenLine className="size-3.5" />
            </div>
            <div className="flex items-center gap-1 rounded-2xl rounded-tl-md bg-paper-100 px-4 py-3 ring-1 ring-paper-200">
              {[0, 150, 300].map((d) => (
                <span key={d} className="size-1.5 animate-bounce rounded-full bg-ink-400" style={{ animationDelay: `${d}ms` }} />
              ))}
            </div>
          </div>
        )}
        <div ref={end} />
      </div>
      <div className="border-t border-paper-200 p-4">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              disabled={busy}
              className="rounded-full bg-white px-2.5 py-1 text-xs text-ink-700 ring-1 ring-paper-300 transition hover:bg-paper-50 hover:ring-brass-400 disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="flex items-center gap-2 rounded-xl bg-paper-50 p-1.5 ring-1 ring-inset ring-paper-200 focus-within:bg-white focus-within:ring-2 focus-within:ring-brass-500">
          <input
            value={text}
            maxLength={MAX_TEXT}
            disabled={busy}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe one change…"
            className="min-w-0 flex-1 bg-transparent px-2 text-sm placeholder:text-ink-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label="Send"
            className="flex size-8 items-center justify-center rounded-lg bg-ink-900 text-white transition hover:bg-ink-800 disabled:opacity-30"
          >
            <ArrowUp className="size-4" />
          </button>
        </form>
      </div>
    </div>
  )
}

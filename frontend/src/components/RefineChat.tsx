import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatMsg } from '../types'
import { MAX_TEXT } from './DescriptionForm'

interface Props {
  chat: ChatMsg[]
  busy: boolean
  onSend: (message: string) => void
  onStartOver: () => void
}

export default function RefineChat({ chat, busy, onSend, onStartOver }: Props) {
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [chat.length])

  function submit(e: FormEvent) {
    e.preventDefault()
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center">
        <h2 className="font-semibold">Refine</h2>
        <button onClick={onStartOver} disabled={busy} className="ml-auto text-sm text-blue-700 hover:underline disabled:opacity-50">
          Start over
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto rounded border bg-slate-50 p-3 text-sm">
        {chat.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex'}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 ${
                m.role === 'user' ? 'bg-slate-900 text-white' : 'bg-white shadow-sm'
              }`}
            >
              {m.content}
            </p>
          </div>
        ))}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={text}
          maxLength={MAX_TEXT}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          placeholder='e.g. "make the jaw wider"'
          className="min-w-0 flex-1 rounded border px-3 py-2 text-sm disabled:bg-slate-50"
        />
        <button type="submit" disabled={busy || !text.trim()} className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  )
}

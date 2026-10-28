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
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-violet" />
          <span className="text-[15px] font-semibold">Refine</span>
        </div>
        <button onClick={onStartOver} disabled={busy} className="text-[13px] text-link hover:text-ink disabled:opacity-50">
          Start over
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pr-0.5">
        {chat.map((m) => {
          const me = m.role === 'user'
          return (
            <div
              key={m.id}
              className={`max-w-[88%] px-3.5 py-3 ${
                me ? 'self-end rounded-[16px_16px_4px_16px] bg-ink text-white' : 'self-start rounded-[16px_16px_16px_4px] bg-tint text-ink'
              }`}
            >
              <div className="mb-1.5 text-[11px] uppercase tracking-[0.06em] opacity-60">{me ? 'Prompt' : 'Assistant'}</div>
              <div className="whitespace-pre-wrap text-[13px] leading-[1.55]">{m.content}</div>
            </div>
          )
        })}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="flex gap-1.5 rounded-2xl bg-tint p-1.5">
        <input
          value={text}
          maxLength={MAX_TEXT}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          placeholder='e.g. "make the jaw wider"'
          className="min-w-0 flex-1 rounded-[10px] border border-transparent bg-transparent p-2.5 text-[13px]"
        />
        <button type="submit" disabled={busy || !text.trim()} className="rounded-[11px] bg-ink px-4 text-[13px] font-medium text-white disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  )
}

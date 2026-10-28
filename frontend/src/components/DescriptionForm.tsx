import { FileText, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button, CardHeader } from './ui'

export const MAX_TEXT = 2000

const CHECKLIST = ['Age & gender', 'Skin tone', 'Face shape', 'Eyes & brows', 'Nose & mouth', 'Hair & facial hair', 'Scars or marks']

interface Props {
  busy: boolean
  replacing: boolean
  onSubmit: (description: string) => void
  onCancel?: () => void
}

export default function DescriptionForm({ busy, replacing, onSubmit, onCancel }: Props) {
  const [text, setText] = useState('')
  const near = text.length > MAX_TEXT * 0.9

  function submit(e: FormEvent) {
    e.preventDefault()
    onSubmit(text.trim())
  }

  return (
    <form onSubmit={submit} className="flex h-full flex-col">
      <CardHeader
        title={replacing ? 'New description' : 'Witness description'}
        icon={<FileText className="size-4" />}
        action={
          onCancel && (
            <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
              Back to chat
            </Button>
          )
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-3 p-5">
        <p className="text-xs text-ink-500">Write what the witness remembers, in their words. Cover as many of these as you can:</p>
        <div className="flex flex-wrap gap-1.5">
          {CHECKLIST.map((c) => (
            <span key={c} className="rounded-md bg-paper-100 px-2 py-0.5 text-[11px] text-ink-500 ring-1 ring-paper-200">
              {c}
            </span>
          ))}
        </div>
        <textarea
          value={text}
          maxLength={MAX_TEXT}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Man, around 30, medium brown skin, square face, small dark eyes, thick eyebrows, broad nose, short black hair, light stubble, scar on the left cheek…"
          className="min-h-48 flex-1 resize-none rounded-xl bg-paper-50 p-4 text-sm leading-relaxed ring-1 ring-inset ring-paper-200 placeholder:text-ink-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brass-500 disabled:opacity-60"
        />
        <div className="flex items-center gap-3">
          <span className={`font-mono text-[11px] ${near ? 'text-amber-600' : 'text-ink-400'}`}>
            {text.length}/{MAX_TEXT}
          </span>
          <Button type="submit" variant="accent" className="ml-auto" disabled={!text.trim()} loading={busy} icon={<Sparkles className="size-4" />}>
            {replacing ? 'Generate new sketch' : 'Generate sketch'}
          </Button>
        </div>
      </div>
    </form>
  )
}

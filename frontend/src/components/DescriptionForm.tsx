import { useState, type FormEvent } from 'react'

export const MAX_TEXT = 2000

interface Props {
  busy: boolean
  replacing: boolean
  onSubmit: (description: string) => void
  onCancel?: () => void
}

export default function DescriptionForm({ busy, replacing, onSubmit, onCancel }: Props) {
  const [text, setText] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    onSubmit(text.trim())
  }

  return (
    <form onSubmit={submit} className="flex h-full flex-col gap-3">
      <h2 className="font-semibold">Witness description</h2>
      <textarea
        value={text}
        maxLength={MAX_TEXT}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe the face: age, skin tone, face shape, eyes, nose, hair, marks…"
        className="min-h-60 flex-1 resize-none rounded border p-3 text-sm disabled:bg-slate-50"
      />
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-500">
          {text.length}/{MAX_TEXT}
        </span>
        {onCancel && (
          <button type="button" onClick={onCancel} disabled={busy} className="ml-auto rounded px-3 py-2 hover:bg-slate-100">
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className={`${onCancel ? '' : 'ml-auto '}rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50`}
        >
          {replacing ? 'Generate new sketch' : 'Generate'}
        </button>
      </div>
    </form>
  )
}

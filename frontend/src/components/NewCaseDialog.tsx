import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MessagesSquare, PenLine, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createCase, startInterview } from '../api'

type Start = 'sketch' | 'interview'

// name the case, then start from a typed description or from a witness interview
export default function NewCaseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const dialog = useRef<HTMLDialogElement>(null)
  const [title, setTitle] = useState('')

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) {
      setTitle('')
      d.showModal()
    } else if (!open && d.open) d.close()
  }, [open])

  const create = useMutation({
    mutationFn: async (start: Start) => {
      const c = await createCase(title.trim() || `New case ${new Date().toLocaleString()}`)
      return { c, iv: start === 'interview' ? await startInterview(c.id) : null }
    },
    onSuccess: ({ c, iv }) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      onClose()
      navigate(iv ? `/cases/${c.id}/interviews/${iv.id}` : `/cases/${c.id}`)
    },
  })

  const option = (start: Start, icon: React.ReactNode, label: string, text: string) => (
    <button
      type="button"
      onClick={() => create.mutate(start)}
      disabled={create.isPending}
      className="flex flex-1 flex-col gap-1.5 rounded-[16px] border border-ink/10 bg-field p-4 text-left hover:border-ink disabled:opacity-50"
    >
      <span className="grid size-9 place-items-center rounded-xl bg-white text-ink">{icon}</span>
      <span className="mt-1 text-[14px] font-semibold">{label}</span>
      <span className="text-[13px] leading-snug text-muted">{text}</span>
    </button>
  )

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(e) => e.target === dialog.current && onClose()}
      className="m-auto w-[min(520px,92vw)] rounded-[24px] border border-ink/10 bg-white p-0 text-ink shadow-[0_30px_80px_-30px_rgba(38,36,31,0.5)] backdrop:bg-ink/25 backdrop:backdrop-blur-[2px]"
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] font-semibold">New case</h2>
          <button type="button" onClick={onClose} title="Close" className="grid size-8 place-items-center rounded-full text-muted hover:bg-tint hover:text-ink">
            <X size={16} />
          </button>
        </div>
        <label className="flex flex-col gap-1.5 text-[13px] text-body">
          Case title
          <input
            autoFocus
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Chain snatching, Hebbal"
            className="rounded-xl border border-line bg-field px-3 py-2.5 text-[14px] text-ink"
          />
        </label>
        <div className="flex gap-3">
          {option('sketch', <PenLine size={16} />, 'Describe the face', "Type the witness's description and draw the sketch")}
          {option('interview', <MessagesSquare size={16} />, 'Witness interview', 'Guided, neutral questions first; the sketch comes after')}
        </div>
        {create.isError && <p className="text-[13px] text-red-600">{create.error.message}</p>}
      </div>
    </dialog>
  )
}

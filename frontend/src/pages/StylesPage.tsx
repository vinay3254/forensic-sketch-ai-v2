import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, Shirt } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { applyStyle, getCase, listStyles } from '../api'
import PageHeader from '../components/PageHeader'

// a FACETTE-style picker: pick a look and it is drawn onto the latest sketch as a new version
export default function StylesPage() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const c = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })
  const catalog = useQuery({ queryKey: ['styles'], queryFn: listStyles, staleTime: Infinity })
  const [tab, setTab] = useState('clothing')
  const [q, setQ] = useState('')
  const [own, setOwn] = useState('')
  const [applying, setApplying] = useState<string | null>(null)

  const apply = useMutation({
    mutationFn: (body: { style: string; label: string } | { category: string; text: string; label: string }) => {
      setApplying(body.label)
      const { label: _label, ...payload } = body
      return applyStyle(caseId, payload as { style: string } | { category: string; text: string })
    },
    onSettled: () => setApplying(null),
    onSuccess: () => {
      setOwn('')
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      queryClient.invalidateQueries({ queryKey: ['cases'] })
    },
  })

  if (c.isPending || catalog.isPending) return <p className="p-4 text-muted">Loading…</p>
  if (c.error || catalog.error) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{(c.error ?? catalog.error)?.message}</p>

  const latest = c.data.versions.at(-1)
  const category = catalog.data.find((x) => x.key === tab) ?? catalog.data[0]
  const shown = q.trim()
    ? catalog.data.flatMap((x) => x.styles.filter((s) => s.label.toLowerCase().includes(q.trim().toLowerCase())))
    : category.styles
  const busy = apply.isPending

  function submitOwn(e: FormEvent) {
    e.preventDefault()
    if (own.trim()) apply.mutate({ category: category.key, text: own.trim(), label: own.trim() })
  }

  return (
    <>
      <PageHeader title="Styles" />
      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,2fr)]">
        <section className="flex min-h-0 flex-col gap-3 rounded-[22px] bg-cream p-4">
          <div className="flex items-center justify-between px-1 text-[13px] text-muted">
            <span>{latest ? `Current sketch · v${latest.version_no}` : 'No sketch yet'}</span>
            {latest?.localized === false && latest.instruction.startsWith('Style:') && <span title="The whole sketch was redrawn">full redraw</span>}
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center [container-type:size]">
            {latest ? (
              <img src={latest.image_url} alt="Current sketch" className="aspect-[2/3] w-[min(100cqw,66.6cqh)] rounded-[14px] object-cover shadow-[0_18px_40px_-20px_rgba(38,36,31,0.4)]" />
            ) : (
              <p className="max-w-56 text-center text-[13px] text-muted">Draw a sketch on the Sketch tab first; styles are applied to it.</p>
            )}
            {busy && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-[14px] bg-cream/85">
                <div className="size-10 animate-spin rounded-full border-4 border-line border-t-ink" />
                <p className="text-[13px] text-body">Applying {applying}… about a minute</p>
              </div>
            )}
          </div>
          {apply.isSuccess && !busy && <p className="rounded-xl bg-white/80 px-3 py-2 text-[13px] text-body">{apply.data.reply} Undo by picking the previous version on the Sketch tab.</p>}
          {apply.isError && <p className="rounded-xl bg-red-50 px-3 py-2 text-[13px] text-red-700">{apply.error.message}</p>}
        </section>

        <section className="flex min-h-0 flex-col gap-4 rounded-[22px] bg-white p-5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1 rounded-full bg-tint p-1">
              {catalog.data.map((x) => (
                <button
                  key={x.key}
                  onClick={() => {
                    setTab(x.key)
                    setQ('')
                  }}
                  className={`rounded-full px-3.5 py-1.5 text-[13px] ${!q && x.key === category.key ? 'bg-ink font-medium text-white' : 'text-body hover:text-ink'}`}
                >
                  {x.label}
                </button>
              ))}
            </div>
            <label className="ml-auto flex w-52 items-center gap-2 rounded-full border border-line bg-white px-3 py-1.5">
              <Search size={14} className="text-faint" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search all styles" className="min-w-0 flex-1 border-0 bg-transparent text-[13px]" />
            </label>
          </div>

          <div className="grid min-h-0 flex-1 auto-rows-max grid-cols-[repeat(auto-fill,minmax(128px,1fr))] gap-3 overflow-y-auto pr-1">
            {shown.map((s) => (
              <button
                key={s.key}
                onClick={() => apply.mutate({ style: s.key, label: s.label })}
                disabled={busy || !latest}
                title={latest ? `Put ${s.label} on the sketch` : 'Draw a sketch first'}
                className="group flex flex-col gap-2 rounded-[16px] border border-ink/10 bg-field p-2 text-left transition hover:-translate-y-0.5 hover:border-ink disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
              >
                {s.image_url ? (
                  <img src={s.image_url} alt="" loading="lazy" className="aspect-square w-full rounded-xl bg-white object-cover" />
                ) : (
                  <span className="grid aspect-square w-full place-items-center rounded-xl bg-white text-ghost">
                    <Shirt size={28} />
                  </span>
                )}
                <span className="px-1 pb-1 text-[13px] font-medium text-ink">{s.label}</span>
              </button>
            ))}
            {shown.length === 0 && <p className="col-span-full py-8 text-center text-[13px] text-muted">No style matches “{q}”.</p>}
          </div>

          <form onSubmit={submitOwn} className="flex gap-2 border-t border-line-soft pt-4">
            <input
              value={own}
              onChange={(e) => setOwn(e.target.value)}
              maxLength={200}
              disabled={busy || !latest}
              placeholder={`Describe your own ${category.label.toLowerCase()}… e.g. “red checked shirt”`}
              className="min-w-0 flex-1 rounded-full border border-line bg-field px-4 py-2.5 text-[13px]"
            />
            <button type="submit" disabled={busy || !latest || !own.trim()} className="rounded-full bg-ink px-5 text-[13px] font-medium text-white hover:bg-ink-2 disabled:opacity-50">
              Apply
            </button>
          </form>
        </section>
      </div>
    </>
  )
}

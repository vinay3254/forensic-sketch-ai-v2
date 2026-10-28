import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getCase, listBodyTypes, listVariants, makeVariant, saveDetails, sheetUrl } from '../api'
import { useBody } from '../components/BodyFigureCard'
import BodyTypeChart, { isBuild } from '../components/BodyTypeChart'
import PageHeader, { btnDark, btnLight } from '../components/PageHeader'
import { VARIANT_KINDS, type Attributes, type CaseDetails, type VariantKind, type Version } from '../types'

const W = 1400
const H = 800

type Row = { k: string; v?: string | null; uncertain?: boolean }
type Block = { title: string; rows: Row[] }

const face = (v: Version, keys: [keyof Attributes, string][], optional: [keyof Attributes, string][] = []): Row[] => [
  ...keys.map(([k, l]) => ({ k: l, v: v.attributes[k], uncertain: v.uncertain.includes(k) })),
  ...optional.filter(([k]) => v.attributes[k]).map(([k, l]) => ({ k: l, v: v.attributes[k], uncertain: v.uncertain.includes(k) })),
]

function blocks(v: Version, d: CaseDetails): [Block[], Block[]] {
  const extra = (pairs: [keyof CaseDetails, string][]) => pairs.filter(([k]) => d[k]).map(([k, l]) => ({ k: l, v: d[k] }))
  return [
    [
      {
        title: 'Physical characteristics',
        rows: face(v, [['gender', 'Gender'], ['age_range', 'Age range'], ['skin_tone', 'Skin tone'], ['face_shape', 'Face shape'], ['hair', 'Hair'], ['eyes', 'Eyes']],
          [['eyebrows', 'Eyebrows'], ['nose', 'Nose'], ['mouth', 'Mouth'], ['ears', 'Ears'], ['jaw', 'Jaw']]),
      },
      { title: 'Secondary characteristics', rows: [...face(v, [['facial_hair', 'Facial hair'], ['accessories', 'Accessories']]), { k: 'Clothing', v: d.clothing }] },
    ],
    [
      {
        title: 'Distinguishing features',
        rows: [...face(v, [['marks', 'Marks'], ['notes', 'Notes']]), ...extra([['movement', 'Movement'], ['voice', 'Voice'], ['other_traits', 'Other traits']])],
      },
      { title: 'Weapon', rows: [{ k: 'Reported', v: d.weapon }] },
      { title: 'Approach', rows: [{ k: 'Reported', v: d.approach }] },
    ],
  ]
}

const label = 'text-[11px] uppercase tracking-[0.08em]'

function BlockCard({ b }: { b: Block }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-[#e7e7e3]">
      <div className={`bg-cream px-3 py-2 font-semibold ${label}`}>{b.title}</div>
      <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 px-3 py-2.5 text-[13px]">
        {b.rows.map((r) => (
          <div key={r.k} className="contents">
            <span className="text-muted">{r.k}</span>
            <span className={r.v ? 'text-ink' : 'text-ghost'}>
              {r.v || '—'}
              {r.uncertain && <span className="ml-1 text-[11px] text-amber-700">(uncertain)</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CaseSheetPage() {
  const caseId = Number(useParams().id)
  const queryClient = useQueryClient()
  const c = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })
  const variants = useQuery({ queryKey: ['variants', caseId], queryFn: () => listVariants(caseId) })
  const types = useQuery({ queryKey: ['body-types'], queryFn: listBodyTypes, staleTime: Infinity })
  const body = useBody(caseId)
  const [pending, setPending] = useState<VariantKind | null>(null)
  const make = useMutation({
    mutationFn: ({ versionId, kind }: { versionId: number; kind: VariantKind }) => {
      setPending(kind)
      return makeVariant(caseId, versionId, kind)
    },
    onSettled: () => {
      setPending(null)
      return queryClient.invalidateQueries({ queryKey: ['variants', caseId] })
    },
  })
  const pickBuild = useMutation({
    mutationFn: (build: string) => saveDetails(caseId, { ...c.data!.case.details, build }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['case', caseId] }),
  })

  // scale the fixed 1400×800 sheet to whatever room the window leaves
  const [k, setK] = useState(0.6)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setK(Math.min(e.contentRect.width / W, e.contentRect.height / H, 1.2)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [c.data])

  if (c.isPending) return <p className="p-4 text-muted">Loading…</p>
  if (c.error) return <p className="rounded-2xl bg-red-50 p-4 text-red-700">{c.error.message}</p>

  const { case: cs, versions } = c.data
  const d = cs.details
  const v = versions.at(-1)
  const crumbs = [{ label: 'Cases', to: '/cases' }, { label: cs.case_number, mono: true, to: `/cases/${caseId}` }, { label: 'Case sheet' }]
  if (!v) {
    return (
      <>
        <PageHeader crumbs={crumbs} title="Case sheet" />
        <p className="rounded-[22px] bg-white p-6 text-[13px] text-muted">Draw a sketch in the workspace first; the case sheet is built from it.</p>
      </>
    )
  }

  const [colA, colB] = blocks(v, d)
  const byKind = new Map((variants.data ?? []).map((x) => [x.kind, x] as const)) // list is newest first
  const shown = [...VARIANT_KINDS].map(([kind, l]) => ({ kind, label: l, variant: [...(variants.data ?? [])].find((x) => x.kind === kind) }))
  const buildType = types.data?.find((t) => isBuild(d.build, t.label))
  const date = new Date().toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <>
      <PageHeader crumbs={crumbs} title="Case sheet" />
      <div className="flex shrink-0 items-center justify-between gap-3 px-2">
        <span className="text-[13px] text-muted">Generated from the sketch, attributes and case details. Uses the latest version, v{v.version_no}.</span>
        <div className="flex gap-2">
          <a href={sheetUrl(caseId, v.id, 'png')} download className={btnLight}>
            Export PNG
          </a>
          <a href={sheetUrl(caseId, v.id, 'pdf')} download className={btnDark}>
            Export PDF
          </a>
        </div>
      </div>
      {make.isError && <p className="shrink-0 rounded-2xl bg-red-50 px-4 py-2 text-[13px] text-red-700">{make.error.message}</p>}
      <div ref={box} className="flex min-h-0 flex-1 items-start justify-center overflow-hidden">
        <div style={{ width: W * k, height: H * k }} className="shrink-0">
          <div style={{ width: W, height: H, transform: `scale(${k})`, transformOrigin: 'top left' }}>
            <section className="box-border flex h-[800px] w-[1400px] flex-col gap-5 rounded-[22px] bg-white px-8 py-7">
              <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-5 border-b-2 border-ink pb-4">
                <div className="flex flex-col gap-1">
                  <span className={`text-muted ${label}`}>Forensic sketch unit</span>
                  <span className="text-[15px] font-semibold">Facial composite</span>
                  <span className="font-mono text-xs text-muted">
                    {cs.case_number} · {date}
                  </span>
                </div>
                <div className="text-[44px] font-semibold leading-none tracking-[-0.03em]">WANTED</div>
                <div className="grid grid-cols-[auto_auto] justify-end gap-x-3 gap-y-1 text-xs">
                  {(
                    [
                      ['Requesting unit', d.requesting_unit],
                      ['Reference no.', d.reference],
                      ['Offence', d.offence],
                    ] as const
                  ).map(([l, val]) => (
                    <div key={l} className="contents">
                      <span className="text-muted">{l}</span>
                      <span className={`max-w-56 truncate ${val ? 'text-ink' : 'text-ghost'}`}>{val || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid h-[400px] grid-cols-[270px_minmax(0,1fr)_minmax(0,1fr)_220px] gap-5">
                <div className="flex flex-col gap-2">
                  <img src={v.image_url} alt="Sketch" className="box-border h-[383px] w-[270px] rounded-xl border border-[#e4e1d6] bg-cream object-cover" />
                  <span className={`text-muted ${label}`}>Original · v{v.version_no}</span>
                </div>
                <div className="flex flex-col gap-3 overflow-hidden">
                  {colA.map((b) => (
                    <BlockCard key={b.title} b={b} />
                  ))}
                </div>
                <div className="flex flex-col gap-3 overflow-hidden">
                  {colB.map((b) => (
                    <BlockCard key={b.title} b={b} />
                  ))}
                </div>
                <div className="flex flex-col overflow-hidden rounded-xl border border-[#e7e7e3]">
                  <div className={`flex justify-between bg-cream px-3 py-2 font-semibold ${label}`}>
                    Build<span className="font-normal normal-case tracking-normal text-body">{d.build || 'Not set'}</span>
                  </div>
                  <div className="grid flex-1 grid-cols-[24px_minmax(0,1fr)] gap-2 p-3">
                    <div className="relative flex items-center justify-center">
                      <div className="absolute inset-y-0 left-1/2 border-l border-ink" />
                      <span className="relative rotate-180 bg-white py-1.5 font-mono text-[10px] text-muted [writing-mode:vertical-rl]">
                        height {d.height || '—'}
                      </span>
                    </div>
                    <div className="flex items-center justify-center overflow-hidden rounded-[10px] bg-field">
                      {body.data ? (
                        <img src={body.data.image_url} alt="Full-body figure" className="max-h-[300px] object-contain mix-blend-multiply" />
                      ) : buildType ? (
                        <img src={buildType.image_url} alt={buildType.label} className="h-[248px] object-contain mix-blend-multiply" />
                      ) : (
                        <span className="px-3 text-center text-xs text-faint">Pick a build in Person &amp; case details</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_420px] gap-6 border-t border-[#efefeb] pt-4">
                <div className="flex flex-col gap-2.5">
                  <div className="flex items-baseline justify-between">
                    <span className={`font-semibold ${label}`}>Post-incident simulations</span>
                    <span className="text-xs text-muted">
                      {byKind.size} of {VARIANT_KINDS.length} generated
                    </span>
                  </div>
                  <div className="grid grid-cols-10 gap-2">
                    {shown.map((s, i) => (
                      <div key={s.kind} className="flex flex-col gap-[5px]">
                        {s.variant ? (
                          <a href={s.variant.image_url} target="_blank" rel="noreferrer" title={`From v${s.variant.version_no}`}>
                            <img src={s.variant.image_url} alt={s.label} className="aspect-[3/4] w-full rounded-[10px] border border-[#e4e1d6] object-cover" />
                          </a>
                        ) : (
                          <button
                            onClick={() => make.mutate({ versionId: v.id, kind: s.kind })}
                            disabled={make.isPending}
                            className="flex aspect-[3/4] w-full flex-col items-center justify-center gap-1 rounded-[10px] border-[1.5px] border-dashed border-[#d6d4cb] text-[11px] text-faint hover:border-violet hover:text-link disabled:cursor-wait"
                          >
                            <span className="font-mono text-[10px]">{String(i + 1).padStart(2, '0')}</span>
                            {pending === s.kind ? (
                              <span className="size-4 animate-spin rounded-full border-2 border-line border-t-violet" />
                            ) : (
                              'Generate'
                            )}
                          </button>
                        )}
                        <span className="truncate text-[11px] text-body">{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-2.5">
                  <span className={`font-semibold ${label}`}>Build comparison</span>
                  <BodyTypeChart compact build={d.build} onPick={(b) => pickBuild.mutate(b)} />
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </>
  )
}

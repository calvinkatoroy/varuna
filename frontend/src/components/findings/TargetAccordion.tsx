import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { SEVS, SEV_CHIP, SEV_LABEL, SEV_LETTER, nextHeaderIndex, type TargetRow } from '@/lib/findings'
import { bare, when } from '@/lib/format'

// One row per target. The header is a button (aria-expanded / aria-controls); the panel is a labelled region.
// Severity is a text label as well as a colour: "2 Critical" from sm up, "2 C" on phones, full words for
// screen readers. Single expand: opening a row closes the other (the parent owns `openId`).
export function TargetAccordion({ targets, openId, staff, onToggle, renderPanel }: {
  targets: TargetRow[]; openId: string | null; staff: boolean
  onToggle: (id: string | null) => void; renderPanel: (t: TargetRow) => ReactNode
}) {
  const root = useRef<HTMLDivElement>(null)

  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const heads = [...(root.current?.querySelectorAll<HTMLButtonElement>('[data-acc-head]') ?? [])]
    const next = nextHeaderIndex(e.key, heads.indexOf(e.currentTarget), heads.length)
    if (next === null) return
    e.preventDefault()
    heads[next]?.focus()
  }

  return (
    <div ref={root}>
      {targets.map((t) => {
        const open = t.task_id === openId
        return (
          <section key={t.task_id} className="border-b border-rule last:border-b-0">
            <h2 className="m-0">
              <button
                type="button"
                id={`acc-h-${t.task_id}`}
                data-acc-head
                aria-expanded={open}
                aria-controls={`acc-p-${t.task_id}`}
                onClick={() => onToggle(open ? null : t.task_id)}
                onKeyDown={onKey}
                className="scroll-mt-24 flex min-h-[56px] w-full items-start gap-3 px-4 py-3.5 text-left hover:bg-panel focus-visible:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5"
              >
                <ChevronDown size={18} aria-hidden className={`mt-1 flex-none text-ink-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    <span className="mono truncate text-[15px] font-semibold text-ink" title={t.target}>{bare(t.target)}</span>
                    {staff && t.org_name && <span className="rounded-md border border-rule bg-panel px-1.5 py-0.5 text-[12px] text-ink-muted">{t.org_name}</span>}
                  </span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                    {SEVS.filter((s) => t.counts[s] > 0).map((s) => (
                      <span key={s} className={`rounded-md px-1.5 py-0.5 text-[12px] font-bold ${SEV_CHIP[s]}`}>
                        <span className="sr-only">{t.counts[s]} {SEV_LABEL[s]}</span>
                        <span aria-hidden>{t.counts[s]} <span className="hidden sm:inline">{SEV_LABEL[s]}</span><span className="sm:hidden">{SEV_LETTER[s]}</span></span>
                      </span>
                    ))}
                    <span className="text-[12px] text-ink-muted">
                      {t.total} findings · {t.total - t.fixed} open{staff && !!t.fp && ` · ${t.fp} false positive${t.fp > 1 ? 's' : ''}`} · scanned {when(t.scanned_at)}
                    </span>
                  </span>
                </span>
              </button>
            </h2>
            <div role="region" id={`acc-p-${t.task_id}`} aria-labelledby={`acc-h-${t.task_id}`} hidden={!open} className="border-t border-rule bg-card">
              {open && renderPanel(t)}
            </div>
          </section>
        )
      })}
    </div>
  )
}

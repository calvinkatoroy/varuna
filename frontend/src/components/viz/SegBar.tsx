// Segmented severity meter (CyberGuard Alerts vocabulary): filled segments show proportion,
// remainder stays faint, count is right aligned and tabular. Colour comes from the data.
export function SegBar({ count, max, tone, label, segs = 16, labelW = 70 }: { count: number; max: number; tone: string; label: string; segs?: number; labelW?: number }) {
  const filled = max > 0 ? Math.round((count / max) * segs) : 0
  return (
    <div className="flex items-center gap-3">
      <span className="flex-none text-[12.5px] text-ink-muted" style={{ width: labelW }}>{label}</span>
      <span className="flex flex-1 gap-[3px]">
        {Array.from({ length: segs }).map((_, i) => (
          <span key={i} className="h-[7px] flex-1 rounded-full transition-colors" style={{ background: i < filled ? `var(--color-${tone})` : 'var(--color-rule)' }} />
        ))}
      </span>
      <span className="mono w-6 flex-none text-right text-[13px] tabular-nums text-ink">{count}</span>
    </div>
  )
}

import { Waves } from 'lucide-react'

// The app's one brand mark: gradient badge + Waves glyph. Varuna is the Vedic god of water/
// oceans - the badge previously used lucide's Shield, which read as "generic security-app
// default" and had nothing to do with the name. Every screen showing the wordmark reuses this
// instead of re-declaring the gradient/shadow/icon inline six separate times.
export function BrandMark({ size = 36, className = '' }: { size?: number; className?: string }) {
  const radius = Math.round(size * 0.3)
  const icon = Math.round(size * 0.53)
  return (
    <span
      className={`grid flex-none place-items-center ${className}`}
      style={{
        width: size, height: size, borderRadius: radius,
        background: 'conic-gradient(from 210deg,#0B5FA5,#4FB3E8,#0B5FA5)',
        boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)',
      }}
    >
      <Waves size={icon} className="text-white" strokeWidth={2.25} />
    </span>
  )
}

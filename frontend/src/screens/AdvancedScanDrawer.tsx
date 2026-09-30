import { useMemo, useState } from 'react'
import { Play, Lock, Search, Bug, Database, Sparkles } from 'lucide-react'
import { Drawer, DrawerContent, DrawerTitle, DrawerClose } from '@/components/ui/drawer'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'

const SEVS = ['info', 'low', 'medium', 'high', 'critical']
const TAGS = ['cves', 'misconfig', 'exposures', 'xss', 'sqli', 'lfi', 'rce', 'takeover']
const TECHS = [['B', 'Boolean'], ['E', 'Error'], ['U', 'Union'], ['S', 'Stacked'], ['T', 'Time'], ['Q', 'Inline']]

type Preset = 'quick' | 'thorough' | 'api' | 'aggressive'

function Section({ icon, title, sub, children }: any) {
  return (
    <section className="border-t border-rule px-6 py-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-panel text-accent">{icon}</span>
        <div>
          <h4 className="text-[14px] font-bold tracking-[-0.01em] text-ink">{title}</h4>
          {sub && <div className="text-[11.5px] text-ink-muted">{sub}</div>}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

function SliderRow({ label, value, suffix, min, max, step, onChange }: any) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-[13px]">
        <span className="text-ink-muted">{label}</span>
        <span className="font-semibold text-ink">{value}{suffix}</span>
      </div>
      <Slider min={min} max={max} step={step} value={[value]} onValueChange={(v: number[]) => onChange(v[0])} />
    </div>
  )
}

const chip = (on: boolean) =>
  `rounded-pill border px-3 py-1.5 text-[12px] font-semibold capitalize transition-colors ${
    on ? 'border-accent bg-accent-soft text-accent-ink' : 'border-rule text-ink-muted hover:text-ink'
  }`

export type ScanOpts = {
  target: string; cookie?: string; depth: number; crawl_duration: number; headless: boolean
  nuclei: { severity: string[]; rate_limit: number; tags: string[] }
  sqlmap: { level: number; risk: number; techniques: string; dump: boolean; os_shell: boolean } | false
}

export function AdvancedScanDrawer({ open, onOpenChange, onLaunch }: { open: boolean; onOpenChange: (v: boolean) => void; onLaunch?: (opts: ScanOpts) => void }) {
  const [preset, setPreset] = useState<Preset | null>('thorough')
  const [target, setTarget] = useState('')
  const [cookie, setCookie] = useState('')
  const [depth, setDepth] = useState(3)
  const [duration, setDuration] = useState(300)
  const [headless, setHeadless] = useState(true)
  const [sev, setSev] = useState<Set<string>>(new Set(['medium', 'high', 'critical']))
  const [rate, setRate] = useState(150)
  const [tags, setTags] = useState<Set<string>>(new Set(['cves', 'misconfig', 'exposures']))
  const [sqlOn, setSqlOn] = useState(true)
  const [level, setLevel] = useState(1)
  const [risk, setRisk] = useState(1)
  const [techs, setTechs] = useState<Set<string>>(new Set(['B', 'E', 'U']))
  const [dump, setDump] = useState(false)
  const [osShell, setOsShell] = useState(false)

  const toggle = (set: Set<string>, v: string, fn: (s: Set<string>) => void) => {
    const n = new Set(set)
    n.has(v) ? n.delete(v) : n.add(v)
    fn(n)
  }

  function applyPreset(p: Preset) {
    setPreset(p)
    if (p === 'quick') { setDepth(2); setDuration(120); setSev(new Set(['high', 'critical'])); setSqlOn(false) }
    if (p === 'thorough') { setDepth(3); setDuration(300); setSev(new Set(['medium', 'high', 'critical'])); setSqlOn(true); setLevel(2); setRisk(1) }
    if (p === 'api') { setDepth(4); setDuration(300); setHeadless(false); setTags(new Set(['cves', 'exposures', 'misconfig'])); setSqlOn(true) }
    if (p === 'aggressive') { setDepth(5); setDuration(600); setSev(new Set(SEVS)); setSqlOn(true); setLevel(5); setRisk(3); setTechs(new Set(['B', 'E', 'U', 'S', 'T', 'Q'])) }
  }

  const opts = useMemo<ScanOpts>(
    () => ({
      target, cookie: cookie || undefined, depth, crawl_duration: duration, headless,
      nuclei: { severity: [...sev], rate_limit: rate, tags: [...tags] },
      sqlmap: sqlOn ? { level, risk, techniques: [...techs].join(''), dump, os_shell: osShell } : false,
    }),
    [target, cookie, depth, duration, headless, sev, rate, tags, sqlOn, level, risk, techs, dump, osShell],
  )

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-w-[520px]">
        <div className="border-b border-rule p-6">
          <span className="text-[12px] font-medium text-ink-muted">Advanced · pentester GUI</span>
          <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">Configure scan</DrawerTitle>
          <div className="mt-4 flex flex-wrap gap-2">
            {(['quick', 'thorough', 'api', 'aggressive'] as Preset[]).map((p) => (
              <button key={p} onClick={() => applyPreset(p)} className={chip(preset === p)}>
                {p === 'aggressive' && <Lock size={11} className="mr-1 inline" />}{p === 'quick' ? 'Quick VA' : p === 'api' ? 'API' : p === 'aggressive' ? 'Aggressive' : 'Thorough Web'}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1">
          <Section icon={<Search size={16} />} title="Target & auth">
            <input className="w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[13px] text-ink outline-none focus:border-accent" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="https://api.acme.io" />
            <input className="w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[13px] text-ink outline-none focus:border-accent" value={cookie} onChange={(e) => setCookie(e.target.value)} placeholder="Cookie / Authorization header (authenticated scan)" />
          </Section>

          <Section icon={<Search size={16} />} title="Discovery" sub="Katana crawl">
            <SliderRow label="Crawl depth" value={depth} min={1} max={5} step={1} onChange={setDepth} />
            <SliderRow label="Crawl duration" value={duration} suffix="s" min={60} max={600} step={30} onChange={setDuration} />
            <div className="flex items-center justify-between"><span className="text-[13px] text-ink-muted">Headless (JS crawl)</span><Switch checked={headless} onCheckedChange={setHeadless} /></div>
          </Section>

          <Section icon={<Bug size={16} />} title="Vulnerability scan" sub="Nuclei">
            <div>
              <div className="mb-2 text-[13px] text-ink-muted">Severity</div>
              <div className="flex flex-wrap gap-2">{SEVS.map((s) => <button key={s} onClick={() => toggle(sev, s, setSev)} className={chip(sev.has(s))}>{s}</button>)}</div>
            </div>
            <SliderRow label="Rate limit" value={rate} suffix="/s" min={10} max={300} step={10} onChange={setRate} />
            <div>
              <div className="mb-2 text-[13px] text-ink-muted">Template tags</div>
              <div className="flex flex-wrap gap-2">{TAGS.map((t) => <button key={t} onClick={() => toggle(tags, t, setTags)} className={chip(tags.has(t))}>{t}</button>)}</div>
            </div>
          </Section>

          <Section icon={<Database size={16} />} title="SQL injection" sub="SQLMap">
            <div className="flex items-center justify-between"><span className="text-[13px] text-ink-muted">Enable SQLMap</span><Switch checked={sqlOn} onCheckedChange={setSqlOn} /></div>
            {sqlOn && (
              <>
                <SliderRow label="Level" value={level} min={1} max={5} step={1} onChange={setLevel} />
                <SliderRow label="Risk" value={risk} min={1} max={3} step={1} onChange={setRisk} />
                <div>
                  <div className="mb-2 text-[13px] text-ink-muted">Techniques</div>
                  <div className="flex flex-wrap gap-2">{TECHS.map(([k, name]) => <button key={k} onClick={() => toggle(techs, k, setTechs)} className={chip(techs.has(k))} title={name}>{k}</button>)}</div>
                </div>
              </>
            )}
          </Section>

          {/* aggressive, gated */}
          <Section icon={<Sparkles size={16} />} title="Aggressive" sub="Destructive, gated by the safe-profile lock">
            <div className="rounded-input border border-dashed border-rule bg-panel/60 p-4">
              <div className="mb-3 flex items-center gap-2 text-[12px] font-semibold text-accent-ink"><Lock size={14} /> Requires lead-pentester approval + explicit opt-in</div>
              <div className="flex items-center justify-between opacity-60"><span className="text-[13px] text-ink-muted">SQLMap --dump (extract DB)</span><Switch checked={dump} onCheckedChange={setDump} disabled /></div>
              <div className="mt-3 flex items-center justify-between opacity-60"><span className="text-[13px] text-ink-muted">SQLMap --os-shell (RCE)</span><Switch checked={osShell} onCheckedChange={setOsShell} disabled /></div>
            </div>
          </Section>

          <details className="border-t border-rule px-6 py-4">
            <summary className="cursor-pointer text-[12px] font-semibold text-ink-muted">Preview opts</summary>
            <pre className="mt-3 overflow-x-auto rounded-input bg-panel p-3 font-mono text-[11px] leading-relaxed text-ink">{JSON.stringify(opts, null, 2)}</pre>
          </details>
        </div>

        <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
          <DrawerClose asChild><Button variant="outline" size="lg" className="flex-1">Cancel</Button></DrawerClose>
          <Button size="lg" className="flex-[2]" disabled={!target.trim()} onClick={() => { onLaunch?.(opts); onOpenChange(false) }}><Play size={16} className="fill-current" /> Launch scan</Button>
        </div>
      </DrawerContent>
    </Drawer>
  )
}

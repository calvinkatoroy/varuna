import { useState } from 'react'
import { api, download } from '../api'
import Button from '../components/Button'

const SEV: Record<string, { cls: string; label: string }> = {
  critical: { cls: 'text-crit', label: 'Critical' },
  high: { cls: 'text-high', label: 'High' },
  medium: { cls: 'text-med', label: 'Medium' },
  low: { cls: 'text-low', label: 'Low' },
  info: { cls: 'text-info', label: 'Info' },
}
const TEMPLATES = ['Executive Summary', 'Full Technical', 'OWASP Web App', 'ILCS Internal']

export default function FindingsReview() {
  const [jobId, setJobId] = useState('')
  const [findings, setFindings] = useState<any[] | null>(null)
  const [template, setTemplate] = useState('Full Technical')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)

  async function load() {
    if (!jobId) return
    setErr('')
    setLoading(true)
    try {
      setFindings(await api.pget(`/api/findings/${jobId}`))
    } catch (e: any) {
      setErr(e.message + ' (private plane requires Tailscale)')
      setFindings(null)
    } finally {
      setLoading(false)
    }
  }

  async function genReport() {
    setGenerating(true)
    try {
      const meta = await api.ppost('/api/reports/generate', { job_id: jobId, template })
      await download(api.privateBase, `/api/reports/${meta.file}/download`, meta.file)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="max-w-3xl space-y-md">
      <h1 className="font-display text-display text-ink">Findings Review</h1>
      <div className="flex gap-xs">
        <input className="input" placeholder="Job ID" value={jobId} onChange={(e) => setJobId(e.target.value)} />
        <Button variant="ghost" busy={loading} busyLabel="Loading…" onClick={load}>
          Load
        </Button>
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}

      {findings && (
        <>
          <div className="flex items-center gap-xs">
            <select className="input flex-1" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {TEMPLATES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <Button busy={generating} busyLabel="Generating…" onClick={genReport}>
              Generate report
            </Button>
          </div>
          {findings.length === 0 && <div className="text-ink-faint">No findings for this job.</div>}
          {findings.map((f, i) => {
            const s = SEV[(f.severity || 'info').toLowerCase()] || SEV.info
            return (
              <details key={i} className="card" open={['critical', 'high'].includes((f.severity || '').toLowerCase())}>
                <summary className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-paper-2 rounded-input">
                  <span className={`font-semibold ${s.cls}`}>{s.label}</span>{' '}
                  <span className="text-ink">{f.name}</span>
                </summary>
                <div className="mt-xs space-y-3xs text-sm text-ink-muted">
                  <div>
                    <span className="text-ink-faint">Host:</span> {f.host} &nbsp;
                    <span className="text-ink-faint">URL:</span> {f.url}
                  </div>
                  {f.owasp && <div><span className="text-ink-faint">OWASP:</span> {f.owasp}</div>}
                  {(f.cve || f.cwe) && (
                    <div className="mono">
                      <span className="text-ink-faint font-body">CVE:</span> {f.cve || '-'}{' '}
                      <span className="text-ink-faint font-body">CVSS:</span> {f.cvss ?? '-'}{' '}
                      <span className="text-ink-faint font-body">CWE:</span> {f.cwe || '-'}
                    </div>
                  )}
                  {f.impact && <div><span className="text-ink-faint">Impact:</span> {f.impact}</div>}
                  {f.remediation && <div><span className="text-ink-faint">Remediation:</span> {f.remediation}</div>}
                  {f.evidence && (
                    <pre className="mono overflow-x-auto rounded-input bg-paper p-xs text-xs text-ink-muted">{f.evidence}</pre>
                  )}
                  <div className="mono text-xs text-ink-faint">tool: {f.tool}</div>
                </div>
              </details>
            )
          })}
        </>
      )}
    </div>
  )
}
